"""Turn collected series into the in-memory report. No I/O."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from ops_dashboard import catalog
from ops_dashboard.format import chart_ticks, chart_ymax, format_number
from ops_dashboard.health import (
    Verdict,
    evaluate_level_window,
    evaluate_ratio_window,
    evaluate_stall,
    evaluate_threshold,
    evaluate_unthresholded,
    freshest_index,
    rollup,
)
from ops_dashboard.model import ChartView, ComponentView, Fact, QueryRecord, Report
from ops_dashboard.profile import SNAPSHOT, Profile
from ops_dashboard.series import count_present, failure_rates, rolling_sum
from ops_dashboard.window import format_pt

SeriesMap = Dict[str, List[Optional[float]]]


@dataclass(frozen=True)
class Ctx:
    profile: Profile
    start: int
    count: int

    @property
    def step(self) -> int:
        return self.profile.step

    def text(self, value: str) -> str:
        return self.profile.localize(value)

    def buckets(self, minutes: int) -> int:
        return self.profile.buckets_for(minutes * 60)


def derive_rates(series: SeriesMap, count: int, window: int = 1) -> None:
    """Failure rates and their request volume, both over the trailing rate window."""
    for rate_key, total_key, failed_key in catalog.RATE_PAIRS:
        totals = _values(series, total_key, count)
        failed = _values(series, failed_key, count)
        series[rate_key] = failure_rates(totals, failed, window)
        series[total_key + "Win"] = rolling_sum(totals, window)


def build_report(
    series: SeriesMap,
    *,
    start: int,
    end: int,
    generated_epoch: int,
    fixture: bool,
    profile: Profile = SNAPSHOT,
    states: Optional[Mapping[str, str]] = None,
    queries: Optional[Sequence[QueryRecord]] = None,
    data_quality: Optional[Sequence[str]] = None,
    unavailable: Optional[Sequence[str]] = None,
) -> Report:
    count = (end - start) // profile.step
    ctx = Ctx(profile, start, count)
    blank = _blank(series, count)
    derive_rates(blank, count, profile.rate_window)
    state_map = {key: value.lower() for key, value in (states or {}).items()}
    components: List[ComponentView] = []
    absent_notes: List[str] = []
    maintenance_note = ""
    for spec in catalog.COMPONENTS:
        if spec.mode == "absent":
            presence = state_map.get(spec.id, "absent" if fixture else "unknown")
            if presence == "present":
                components.append(_unscored_present(spec, count))
            elif presence == "absent":
                absent_notes.append(
                    "Public API. wts-prod-publicapi is absent from resource group wts-prod. "
                    "It is omitted from the map, not scored, and not shown as healthy."
                )
            else:
                absent_notes.append(
                    "Public API. Presence of wts-prod-publicapi could not be confirmed. "
                    "It is omitted from the map and is not shown as healthy."
                )
            continue
        view, note = _component(
            spec,
            blank,
            ctx,
            state_map.get(spec.id, "running"),
            fixture,
            set(unavailable or ()),
        )
        components.append(view)
        if note:
            maintenance_note = note
    return Report(
        schema_version=catalog.SCHEMA_VERSION,
        generated_epoch=generated_epoch,
        window_start=start,
        window_end=end,
        step=profile.step,
        count=count,
        fixture=fixture,
        components=components,
        edges=catalog.EDGES,
        series={key: blank.get(key, [None] * count) for key in catalog.all_series_keys()},
        queries=list(queries or []),
        data_quality=list(data_quality or []),
        absent_notes=absent_notes,
        maintenance_note=maintenance_note,
        profile=profile.name,
        latest_sample=_latest_sample(blank, start, profile.step),
    )


def _latest_sample(series: SeriesMap, start: int, step: int) -> Optional[int]:
    """Newest bucket with an Azure Monitor value. Shows how far Azure trails the window end."""
    newest = None
    for key in catalog.metric_keys():
        values = series.get(key)
        if not values:
            continue
        for index in range(len(values) - 1, -1, -1):
            if values[index] is not None:
                if newest is None or index > newest:
                    newest = index
                break
    return None if newest is None else start + newest * step


def _blank(series: SeriesMap, count: int) -> SeriesMap:
    filled: SeriesMap = {}
    for key in catalog.all_series_keys():
        values = series.get(key)
        if values is None:
            filled[key] = [None] * count
            continue
        if len(values) != count:
            raise ValueError(f"{key} has {len(values)} samples, expected {count}")
        filled[key] = list(values)
    for key, values in series.items():
        if key not in filled:
            if len(values) != count:
                raise ValueError(f"{key} has {len(values)} samples, expected {count}")
            filled[key] = list(values)
    return filled


def _values(series: SeriesMap, key: str, count: int) -> List[Optional[float]]:
    values = series.get(key)
    if values is None:
        return [None] * count
    return values


def _fmt_for(spec: catalog.Component, metric: Optional[str]) -> str:
    for rule in spec.rules:
        if rule.series == metric:
            return rule.fmt
    for display in (*spec.displays, *spec.facts):
        if display.series == metric:
            return display.fmt
    return "pct1"


def _component(spec, series, ctx: Ctx, app_state, fixture, unavailable):
    start, count = ctx.start, ctx.count
    freshness = ctx.profile.freshness
    verdicts: List[Verdict] = []
    if app_state == "stopped":
        verdicts.append(
            Verdict(
                "unknown",
                f"App Service state is Stopped for {spec.resource}. It is not marked healthy.",
                None,
                None,
                "appState",
                None,
            )
        )
    if spec.mode == "unthresholded":
        primary = next((item.series for item in spec.displays if item.series), spec.id)
        verdicts.append(
            evaluate_unthresholded(
                _values(series, primary, count),
                noun=spec.title,
                metric=primary,
                freshness=freshness,
                step=ctx.step,
            )
        )
    else:
        if spec.reliability == "sparse" and spec.request_series:
            present = count_present(_values(series, spec.request_series, count))
            verdicts.append(
                Verdict(
                    "unknown",
                    (
                        f"Request reliability is unknown. {present:,} of {count:,} buckets have "
                        f"request telemetry, which is too sparse to score at {ctx.profile.bucket_label} resolution."
                    ),
                    None,
                    None,
                    spec.request_series,
                    None,
                )
            )
        for rule in spec.rules:
            if rule.series in unavailable:
                continue
            verdicts.append(_threshold_verdict(rule, series, ctx))
        if spec.id == "sb":
            verdicts.append(
                evaluate_stall(
                    _values(series, "cdcIn", count),
                    _values(series, "cdcOut", count),
                    buckets=ctx.buckets(catalog.CDC_STALL_MINUTES),
                    start=start,
                    step=ctx.step,
                )
            )
        if spec.id == "searchapi":
            verdicts.extend(_comvoy_rule_verdicts(series, ctx))
    verdict = rollup(verdicts)
    note = ""
    if fixture and spec.fixture_maintenance and verdict.state == "healthy":
        note = (
            "Fixture only: the data-change tracker is drawn as maintenance to show that state. "
            "Live runs do not invent a maintenance window."
        )
        verdict = Verdict("maintenance", note + " " + verdict.reason, verdict.threshold, verdict.evaluated_epoch, verdict.metric, verdict.value)
    if verdict.metric and verdict.state in ("critical", "degraded", "healthy"):
        peak_value, peak_epoch = _peak(_values(series, verdict.metric, count), start, ctx.step)
        if peak_epoch is not None and peak_value is not None and peak_value != verdict.value:
            fmt = _fmt_for(spec, verdict.metric)
            verdict = Verdict(
                verdict.state,
                verdict.reason + f" Peak in the window is {format_number(peak_value, fmt)} at {format_pt(peak_epoch)}.",
                verdict.threshold,
                verdict.evaluated_epoch,
                verdict.metric,
                verdict.value,
            )
    displays = [_fact(item, series, ctx) for item in spec.displays]
    while len(displays) < 3:
        displays.append(Fact("", ""))
    charts = [_chart(item, spec, series, ctx) for item in spec.charts]
    present = (
        charts[0].present
        if charts
        else count_present(_values(series, spec.request_series or "", count) if spec.request_series else [None] * count)
    )
    return (
        ComponentView(
            id=spec.id,
            title=spec.title,
            layer=spec.layer,
            row=spec.row,
            stack=spec.stack,
            icon=spec.icon,
            runtime=spec.runtime,
            resource=spec.resource,
            share=spec.share,
            state=verdict.state,
            reason=verdict.reason,
            threshold=verdict.threshold,
            evaluated_epoch=verdict.evaluated_epoch,
            dominant=displays[0],
            secondary=displays[1],
            also=displays[2],
            facts=[_fact(item, series, ctx) for item in spec.facts],
            charts=charts,
            samples_present=present,
            samples_expected=count,
            on_map=True,
        ),
        note,
    )


def _unscored_present(spec, count: int) -> ComponentView:
    verdict = Verdict(
        "unknown",
        "wts-prod-publicapi is present. It has no scored metric set in this report, so it is not healthy.",
        None,
        None,
        None,
        None,
    )
    return ComponentView(
        id=spec.id,
        title=spec.title,
        layer=spec.layer,
        row=spec.row,
        stack=spec.stack,
        icon=spec.icon,
        runtime=spec.runtime,
        resource=spec.resource,
        share=None,
        state=verdict.state,
        reason=verdict.reason,
        threshold=None,
        evaluated_epoch=None,
        dominant=Fact("presence", "Present"),
        secondary=Fact("", "Not scored"),
        also=Fact("", ""),
        facts=[],
        charts=[],
        samples_present=0,
        samples_expected=count,
        on_map=True,
    )


def _threshold_verdict(rule: catalog.ThresholdRule, series, ctx: Ctx) -> Verdict:
    formatter = lambda value, fmt=rule.fmt: format_number(value, fmt)  # noqa: E731
    volume = None
    if rule.volume_series:
        # Rates are judged over the trailing rate window, so the volume guard uses the same window.
        windowed = rule.volume_series + "Win"
        volume = _values(series, windowed if windowed in series else rule.volume_series, ctx.count)
    return evaluate_threshold(
        _values(series, rule.series, ctx.count),
        metric=rule.series,
        noun=rule.noun,
        warning=rule.warning,
        critical=rule.critical,
        op=rule.op,
        format_value=formatter,
        start=ctx.start,
        step=ctx.step,
        volume=volume,
        min_volume=rule.min_volume,
        freshness=ctx.profile.freshness,
    )


def _comvoy_rule_verdicts(series, ctx: Ctx) -> List[Verdict]:
    pct = lambda value: format_number(value, "pct1")  # noqa: E731
    integer = lambda value: format_number(value, "int")  # noqa: E731
    start, step, count = ctx.start, ctx.step, ctx.count
    return [
        evaluate_ratio_window(
            _values(series, "srpReq", count),
            _values(series, "srpFail", count),
            metric="srpFailPct",
            noun="Comvoy search-results failure rate",
            buckets=ctx.buckets(catalog.COMVOY_SRP_MINUTES),
            min_total=catalog.COMVOY_SRP_MIN_REQUESTS,
            limit=catalog.COMVOY_SRP_FAIL_PCT,
            state_on_breach="critical",
            format_value=pct,
            start=start,
            step=step,
        ),
        evaluate_level_window(
            _values(series, "srpReq", count),
            metric="srpVolume",
            noun="Comvoy search-results volume",
            buckets=ctx.buckets(catalog.COMVOY_SRP_VOLUME_MINUTES),
            limit=catalog.COMVOY_SRP_VOLUME,
            state_on_breach="degraded",
            format_value=integer,
            start=start,
            step=step,
        ),
        evaluate_ratio_window(
            _values(series, "leadReq", count),
            _values(series, "leadFail", count),
            metric="leadFailPct",
            noun="SubmitLead failure rate",
            buckets=ctx.buckets(catalog.COMVOY_LEAD_MINUTES),
            min_total=catalog.COMVOY_LEAD_MIN_REQUESTS,
            limit=catalog.COMVOY_LEAD_FAIL_PCT,
            state_on_breach="critical",
            format_value=pct,
            start=start,
            step=step,
        ),
    ]


def _peak(values: Sequence[Optional[float]], start: int, step: int) -> Tuple[Optional[float], Optional[int]]:
    best = None
    index = None
    for cursor, value in enumerate(values):
        if value is None:
            continue
        if best is None or value > best:
            best = value
            index = cursor
    if index is None:
        return None, None
    return best, start + index * step


def _quantile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    position = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[position]


def _fact(spec: catalog.Display, series, ctx: Ctx) -> Fact:
    unit = ctx.text(spec.unit)
    if spec.reduce == "literal":
        return Fact(unit, spec.literal or "")
    values = _values(series, spec.series or "", ctx.count)
    if spec.reduce == "completeness":
        return Fact(unit, f"{count_present(values):,} of {ctx.count:,}")
    if spec.reduce == "sum":
        if all(value is None for value in values):
            return Fact(unit, "No sample")
        return Fact(unit, format_number(sum(value or 0 for value in values), spec.fmt))
    if spec.reduce == "peak":
        best, _ = _peak(values, 0, ctx.step)
        return Fact(unit, format_number(best, spec.fmt))
    index = freshest_index(values, ctx.profile.freshness)
    value = None if index is None else values[index]
    return Fact(unit, format_number(value, spec.fmt))


def _chart(spec: catalog.ChartSpec, component, series, ctx: Ctx) -> ChartView:
    count = ctx.count
    keys = [key for key, _name in spec.series]
    limits = []
    thresholds = []
    seen = set()
    for other in catalog.COMPONENTS:
        for rule in other.rules:
            if rule.series not in keys:
                continue
            for kind, limit in (("warn", rule.warning), ("crit", rule.critical)):
                if limit is None or limit == 0 or (kind, limit) in seen:
                    continue
                seen.add((kind, limit))
                limits.append(limit)
                name = "Warning" if kind == "warn" else "Critical"
                thresholds.append({"y": limit, "kind": kind, "name": f"{name} {format_number(limit, spec.fmt)}"})
    columns = [_values(series, key, count) for key in keys]
    present_values = [value for column in columns for value in column if value is not None]
    peak = max(present_values) if present_values else 0.0
    axis_peak = peak
    if spec.cap_quantile and present_values:
        axis_peak = min(peak, _quantile(present_values, spec.cap_quantile))
    y_max = chart_ymax([axis_peak], limits, spec.scale)
    note = ctx.text(spec.note)
    if peak > y_max:
        note += (
            f" The axis stops at {format_number(y_max, spec.fmt)} so typical values stay readable. "
            f"The peak of {format_number(peak, spec.fmt)} is drawn at the top edge."
        )
    present = 0
    for index in range(count):
        if any(column[index] is not None for column in columns):
            present += 1
    return ChartView(
        id=spec.id,
        caption=ctx.text(spec.caption),
        fmt=spec.fmt,
        y_max=y_max,
        ticks=chart_ticks(y_max),
        series=list(spec.series),
        thresholds=thresholds,
        volume=spec.volume,
        sum_series=spec.sum_series,
        note=note,
        present=present,
        expected=count,
    )
