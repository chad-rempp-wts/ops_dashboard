"""Health evaluation. Missing or stale data is unknown, never healthy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from ops_dashboard.profile import FRESHNESS_SECONDS
from ops_dashboard.series import trailing_sum

RANK = {
    "healthy": 0,
    "maintenance": 1,
    "unknown": 2,
    "degraded": 3,
    "critical": 4,
}

# Five-minute default. Callers running other bucket sizes pass profile.freshness.
FRESHNESS_BUCKETS = 2


@dataclass(frozen=True)
class Verdict:
    state: str
    reason: str
    threshold: Optional[str]
    evaluated_epoch: Optional[int]
    metric: Optional[str]
    value: Optional[float]


def freshest_index(values: Sequence[Optional[float]], freshness: int = FRESHNESS_BUCKETS) -> Optional[int]:
    count = len(values)
    for offset in range(freshness):
        index = count - 1 - offset
        if index < 0:
            break
        if values[index] is not None:
            return index
    return None


def freshness_for(step: int) -> int:
    """Buckets a sample may trail the window end and still count as current."""
    return max(1, FRESHNESS_SECONDS // step)


def _hits(value: float, limit: Optional[float], op: str) -> bool:
    if limit is None:
        return False
    if op == "gt":
        return value > limit
    if op == "gte":
        return value >= limit
    raise ValueError(f"unsupported operator {op}")


def _limit_text(limit: Optional[float], fmt_value) -> str:
    if limit is None:
        return ""
    return fmt_value(limit)


def evaluate_threshold(
    values: Sequence[Optional[float]],
    *,
    metric: str,
    noun: str,
    warning: Optional[float],
    critical: Optional[float],
    op: str,
    format_value,
    start: int,
    step: int,
    volume: Optional[Sequence[Optional[float]]] = None,
    min_volume: Optional[float] = None,
    freshness: Optional[int] = None,
) -> Verdict:
    if freshness is None:
        freshness = freshness_for(step)
    index = freshest_index(values, freshness)
    window = freshness * step // 60
    if index is None:
        return Verdict(
            "unknown",
            f"{noun} has no sample in the last {window} minutes, so it is unknown.",
            _threshold_phrase(warning, critical, op, format_value),
            None,
            metric,
            None,
        )
    value = float(values[index])  # type: ignore[arg-type]
    epoch = start + index * step
    threshold = _threshold_phrase(warning, critical, op, format_value)
    if min_volume is not None:
        current = None if volume is None or index >= len(volume) else volume[index]
        if current is None or current < min_volume:
            shown = "no request sample" if current is None else f"{int(round(current))} requests"
            return Verdict(
                "unknown",
                (
                    f"{noun} is {format_value(value)} but the window has {shown}, "
                    f"under the minimum of {int(min_volume)} requests, so it is unknown."
                ),
                threshold,
                epoch,
                metric,
                value,
            )
    if _hits(value, critical, op):
        state = "critical"
    elif _hits(value, warning, op):
        state = "degraded"
    else:
        state = "healthy"
    relation = "above" if state in ("degraded", "critical") else "within"
    return Verdict(
        state,
        f"{noun} is {format_value(value)}, {relation} the scoring line. {threshold}".strip(),
        threshold,
        epoch,
        metric,
        value,
    )


def evaluate_stall(
    incoming: Sequence[Optional[float]],
    outgoing: Sequence[Optional[float]],
    *,
    buckets: int,
    start: int,
    step: int,
    noun: str = "CDC consumer",
) -> Verdict:
    """Critical when messages arrived over the window and none were delivered.

    The window ends at the newest bucket where both counts exist, because Azure Monitor
    trails real time by a few minutes. A gap inside the window is unknown.
    """
    minutes = buckets * step // 60
    rule = f"Critical when incoming > 0 and outgoing = 0 for {minutes} minutes."
    if len(incoming) < buckets or len(outgoing) < buckets:
        return Verdict("unknown", f"{noun} stall inputs are shorter than {buckets} buckets.", None, None, "cdcStall", None)
    anchor = None
    limit = min(len(incoming), len(outgoing))
    for index in range(limit - 1, max(-1, limit - 1 - freshness_for(step)), -1):
        if incoming[index] is not None and outgoing[index] is not None:
            anchor = index
            break
    if anchor is None or anchor + 1 < buckets:
        anchor = limit - 1
    epoch = start + anchor * step
    inn = list(incoming[anchor + 1 - buckets : anchor + 1])
    out = list(outgoing[anchor + 1 - buckets : anchor + 1])
    if any(value is None for value in inn + out):
        return Verdict(
            "unknown",
            f"{noun} is unknown because part of the last {minutes} minutes has no Service Bus sample.",
            rule,
            epoch,
            "cdcStall",
            None,
        )
    stalled = sum(float(value) for value in inn) > 0 and sum(float(value) for value in out) <= 0
    if stalled:
        return Verdict(
            "critical",
            f"{noun} is critical: data-changes received messages and delivered none for {minutes} minutes.",
            rule,
            epoch,
            "cdcStall",
            1.0,
        )
    return Verdict(
        "healthy",
        f"{noun} is not stalled over the last {minutes} minutes.",
        rule,
        epoch,
        "cdcStall",
        0.0,
    )


def evaluate_ratio_window(
    totals: Sequence[Optional[float]],
    failed: Sequence[Optional[float]],
    *,
    metric: str,
    noun: str,
    buckets: int,
    min_total: float,
    limit: float,
    state_on_breach: str,
    format_value,
    start: int,
    step: int,
) -> Verdict:
    total = trailing_sum(totals, buckets)
    fail = trailing_sum(failed, buckets)
    minutes = buckets * step // 60
    epoch = start + (len(totals) - 1) * step if totals else None
    threshold = f"{state_on_breach.capitalize()} above {format_value(limit)} over {minutes} minutes when volume is at least {int(min_total)}."
    if total is None or fail is None:
        return Verdict(
            "unknown",
            f"{noun} is unknown because the last {minutes} minutes include a gap.",
            threshold,
            epoch,
            metric,
            None,
        )
    if total < min_total:
        return Verdict(
            "healthy",
            (
                f"{noun} is not scored as a breach: {int(round(total))} requests in {minutes} minutes "
                f"is under the rule minimum of {int(min_total)}."
            ),
            threshold,
            epoch,
            metric,
            None,
        )
    rate = 100.0 * fail / total if total else 0.0
    if rate > limit:
        return Verdict(
            state_on_breach,
            f"{noun} is {format_value(rate)} over {minutes} minutes ({int(round(total))} requests).",
            threshold,
            epoch,
            metric,
            rate,
        )
    return Verdict(
        "healthy",
        f"{noun} is {format_value(rate)} over {minutes} minutes, within the line.",
        threshold,
        epoch,
        metric,
        rate,
    )


def evaluate_level_window(
    totals: Sequence[Optional[float]],
    *,
    metric: str,
    noun: str,
    buckets: int,
    limit: float,
    state_on_breach: str,
    format_value,
    start: int,
    step: int,
) -> Verdict:
    total = trailing_sum(totals, buckets)
    minutes = buckets * step // 60
    epoch = start + (len(totals) - 1) * step if totals else None
    threshold = f"{state_on_breach.capitalize()} above {format_value(limit)} in {minutes} minutes."
    if total is None:
        return Verdict("unknown", f"{noun} is unknown because the last {minutes} minutes include a gap.", threshold, epoch, metric, None)
    if total > limit:
        return Verdict(
            state_on_breach,
            f"{noun} is {format_value(total)} in {minutes} minutes.",
            threshold,
            epoch,
            metric,
            total,
        )
    return Verdict(
        "healthy",
        f"{noun} is {format_value(total)} in {minutes} minutes, within the line.",
        threshold,
        epoch,
        metric,
        total,
    )


def evaluate_unthresholded(
    values: Sequence[Optional[float]],
    *,
    noun: str,
    metric: str,
    freshness: int = FRESHNESS_BUCKETS,
    step: int = 300,
) -> Verdict:
    index = freshest_index(values, freshness)
    if index is None:
        return Verdict(
            "unknown",
            f"{noun} has no sample in the last {freshness * step // 60} minutes, and no scoring threshold is configured.",
            "No scoring threshold is configured.",
            None,
            metric,
            None,
        )
    return Verdict(
        "unknown",
        f"{noun} has a fresh sample. No scoring threshold is configured, so it is not marked healthy.",
        "No scoring threshold is configured.",
        None,
        metric,
        float(values[index]),  # type: ignore[arg-type]
    )


def rollup(verdicts: Sequence[Verdict]) -> Verdict:
    if not verdicts:
        return Verdict("unknown", "No health rule is configured, so this component is unknown.", None, None, None, None)
    winner = verdicts[0]
    for verdict in verdicts[1:]:
        if RANK[verdict.state] > RANK[winner.state]:
            winner = verdict
    extras = [item.reason for item in verdicts if item is not winner and item.state != "healthy"]
    reason = winner.reason
    if extras:
        reason = reason + " Also: " + " ".join(extras[:2])
    return Verdict(
        winner.state,
        reason,
        winner.threshold,
        winner.evaluated_epoch,
        winner.metric,
        winner.value,
    )


def _threshold_phrase(warning: Optional[float], critical: Optional[float], op: str, format_value) -> str:
    word = "above" if op == "gt" else "at or above"
    parts = []
    if warning is not None:
        parts.append(f"Degraded {word} {format_value(warning)}")
    if critical is not None:
        parts.append(f"Critical {word} {format_value(critical)}")
    if not parts:
        return "No scoring threshold is configured."
    return ". ".join(parts) + "."
