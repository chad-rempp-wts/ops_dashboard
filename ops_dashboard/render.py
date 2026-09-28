"""HTML renderer. The snapshot page inlines CSS, script, and data and needs no network.

Live pages add one more inline script that polls the local server. That script is not
present in the snapshot file, so the file uploaded to Blob Storage never makes a request.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path

from ops_dashboard import catalog
from ops_dashboard.format import format_number
from ops_dashboard.health import RANK
from ops_dashboard.icons import LABELS, badge_svg, icon_svg
from ops_dashboard.model import ChartView, ComponentView, Report
from ops_dashboard.profile import FRESHNESS_SECONDS, PROFILES
from ops_dashboard.window import format_pt, format_pt_date, format_pt_long, iso_utc

_ASSETS = Path(__file__).parent / "assets"
_ID = re.compile(r"^[A-Za-z0-9-]+$")
_STATE_ORDER = ("critical", "degraded", "unknown", "maintenance", "healthy")
PRODUCT = "Ops dashboard"


@dataclass(frozen=True)
class Parts:
    """Everything that changes between refreshes: the visible body and the chart data."""

    title: str
    body: str
    payload: dict


def render_parts(report: Report) -> Parts:
    day = format_pt_date(report.window_end)
    return Parts(
        title=f"{PRODUCT} — Production — {day}",
        body=_body(report),
        payload=_chart_payload(report),
    )


def render_html(report: Report, *, live: bool = False, version: str = "") -> str:
    return page(render_parts(report), live=live, version=version)


def page(parts: Parts, *, live: bool = False, version: str = "") -> str:
    css = (_ASSETS / "report.css").read_text(encoding="utf-8")
    script = (_ASSETS / "report.js").read_text(encoding="utf-8")
    live_script = ""
    if live:
        live_script = f"<script>\n{(_ASSETS / 'live.js').read_text(encoding='utf-8')}</script>\n"
    mode = "live" if live else "snapshot"
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en" data-theme="dark">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_text(parts.title)}</title>\n"
        f"<style>\n{css}</style>\n"
        "</head>\n"
        f'<body data-view="map" data-mode="{mode}" data-version="{_attr(version)}">\n'
        f'<div id="app">{parts.body}</div>\n'
        f'<script type="application/json" id="report-data">{_json(parts.payload)}</script>\n'
        f"<script>\n{script}</script>\n"
        f"{live_script}"
        "</body>\n"
        "</html>\n"
    )


def write_report(report: Report, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    html = render_html(report)
    day = format_pt_date(report.window_end)
    dated = out_dir / f"ops-dashboard-{day}.html"
    latest = out_dir / "latest.html"
    dated.write_text(html, encoding="utf-8")
    latest.write_text(html, encoding="utf-8")
    return dated, latest


def _body(report: Report) -> str:
    profile = PROFILES[report.profile]
    scored = [item for item in report.components if item.on_map]
    counts = {state: 0 for state in _STATE_ORDER}
    for item in scored:
        counts[item.state] = counts.get(item.state, 0) + 1
    if report.fixture:
        kind = "Fixture"
        lede = (
            "Fixture data for an offline demo. Health rules match the live report. "
            "Unthresholded components stay unknown. The maintenance state on the data-change tracker is illustrative."
        )
    elif profile.live:
        kind = "Live"
        lede = (
            f"Read-only production measurements at {profile.bucket_label} resolution for the last {profile.span_label}. "
            "A local server queries Azure every minute and this page follows it."
        )
    else:
        kind = "Snapshot"
        lede = "Read-only production measurements. Each run queries Azure and writes this file. Nothing is stored between runs."
    latest = (
        f"<li>Latest Azure sample {_text(format_pt(report.latest_sample))}</li>"
        if report.latest_sample is not None
        else ""
    )
    pill = (
        '<span id="live-pill" class="live-pill" data-state="connecting">Connecting</span>'
        if profile.live
        else ""
    )
    parts = [
        '<a class="skip" href="#summary">Skip to summary</a>',
        '<header class="top"><div class="top-inner">',
        f'<p class="product">{PRODUCT}</p>',
        f'<p class="top-meta">{_text(kind)} · Production · {format_pt_date(report.window_end)}</p>',
        pill,
        '<button type="button" id="theme" aria-pressed="false">Switch to light mode</button>',
        "</div></header>",
        "<main>",
        f"<h1>{PRODUCT}</h1>",
        f'<p class="lede">{_text(lede)} Environment: Production. Generated {_text(format_pt(report.generated_epoch))}.</p>',
        '<ul class="chips">',
        f"<li>{_text(kind)}</li><li>Production</li>",
        f"<li>Generated {_text(format_pt_date(report.generated_epoch))}</li>",
        f"<li>{report.count:,} {_text(profile.bucket_label)} buckets</li>",
        latest,
        "</ul>",
        (
            f'<p class="window">Window <time datetime="{iso_utc(report.window_start)}">'
            f"{_text(format_pt(report.window_start))}</time> through "
            f'<time datetime="{iso_utc(report.window_end)}">{_text(format_pt(report.window_end))}</time>'
            f" · {report.count:,} {_text(profile.bucket_label)} buckets · America/Los_Angeles</p>"
        ),
        '<noscript><p class="noscript">Charts and dependency lines use the script in this file. The page does not load anything from the network.</p></noscript>',
        _summary(counts),
        _attention(scored),
        _architecture(report, scored),
        _table(scored),
        _details(report, scored),
        "</main>",
        _footer(report),
    ]
    return "\n".join(part for part in parts if part)


def _summary(counts: dict) -> str:
    tiles = []
    for state in _STATE_ORDER:
        tiles.append(
            f'<div class="tile is-{state}">{_badge(state)}<p class="count num">{counts.get(state, 0)}</p></div>'
        )
    return '<section class="section" id="summary"><h2>Summary</h2><div class="summary-grid">' + "".join(tiles) + "</div></section>"


def _attention(components: list) -> str:
    rows = [item for item in components if item.state in ("critical", "degraded", "unknown")]
    rows.sort(key=lambda item: (-RANK[item.state], item.title))
    if not rows:
        items = '<li class="attn is-healthy"><p class="attn-title">Nothing in critical, degraded, or unknown.</p></li>'
    else:
        blocks = []
        for item in rows:
            blocks.append(
                f'<li class="attn is-{item.state}"><a href="#{_id(item.id)}">{_badge(item.state)}'
                f'<span class="attn-title">{_text(item.title)}</span>'
                f'<span class="attn-why">{_text(item.reason)}</span></a></li>'
            )
        items = "".join(blocks)
    note = "Critical, degraded, and unknown only. Maintenance stays on the component. Healthy components stay on the map."
    return (
        '<section class="section" id="attention"><h2>Needs attention</h2>'
        f'<p class="map-note">{note}</p><ul class="attn-list">{items}</ul></section>'
    )


def _architecture(report: Report, components: list) -> str:
    cells = [
        '<div class="colhead r1 c2">Dealer and marketplace</div>',
        '<svg id="links" aria-hidden="true"></svg>',
        '<div class="spine" aria-hidden="true"></div>',
        '<div class="colhead r1 c4">CRM</div>',
    ]
    quiet = {
        (3, "crm"): "No separate CRM presentation app in this report.",
    }
    for row, label in (
        (2, "Edge"),
        (3, "Presentation"),
        (4, "APIs"),
        (5, "Workers"),
        (6, "Messaging"),
        (7, "Data and platform"),
    ):
        cells.append(f'<div class="lane r{row} c1">{label}</div>')
        for stack, column in (("wts", "c2"), ("crm", "c4")):
            nodes = [item for item in components if item.row == row and item.stack == stack and item.on_map]
            inner = "".join(_node(item) for item in nodes)
            if not inner:
                message = quiet.get((row, stack), "None in this report.")
                inner = f'<p class="quiet">{_text(message)}</p>'
            else:
                inner = f'<div class="nodes">{inner}</div>'
            cells.append(
                f'<div class="cell r{row} {column}"><p class="cell-kicker">{label}</p>{inner}</div>'
            )
    notes = "".join(f'<p class="absent-note" id="public-api"><strong>Public API.</strong> {_text(note.replace("Public API. ", ""))}</p>' for note in report.absent_notes)
    switch = (
        '<div class="view-switch">'
        '<button type="button" id="show-map" aria-pressed="true">Architecture map</button>'
        '<button type="button" id="show-list" aria-pressed="false">Component list</button>'
        "</div>"
    )
    return (
        '<section class="section" id="architecture"><h2>Architecture</h2>'
        f"{switch}<div class=\"board\">{''.join(cells)}</div>{notes}</section>"
    )


def _node(item: ComponentView) -> str:
    share = f'<span class="share">{_text(item.share)}</span>' if item.share else ""
    resource = f"{item.resource} · {item.runtime}"
    return (
        f'<a class="node is-{item.state}" href="#{_id(item.id)}" data-id="{_id(item.id)}">'
        f'<span class="node-top"><span class="ico">{icon_svg(item.icon)}</span>{_badge(item.state)}</span>'
        f'<span class="node-title">{_text(item.title)}</span>'
        f'<span class="node-resource">{_text(resource)}</span>'
        f"{share}"
        f'<span class="metric"><span class="num">{_text(item.dominant.text)}</span> {_text(item.dominant.label)}</span>'
        f'<span class="sub"><span class="num">{_text(item.secondary.text)}</span> {_text(item.secondary.label)}</span>'
        "</a>"
    )


def _table(components: list) -> str:
    rows = []
    for item in components:
        rows.append(
            "<tr>"
            f'<td><a href="#{_id(item.id)}">{_text(item.title)}</a><div class="resource">{_text(item.resource)}</div></td>'
            f"<td>{_text(item.layer)}</td>"
            f"<td>{_badge(item.state)}</td>"
            f'<td class="num">{_text(item.dominant.text)} <span class="unit">{_text(item.dominant.label)}</span></td>'
            f'<td class="num">{_text(item.secondary.text)} <span class="unit">{_text(item.secondary.label)}</span></td>'
            f'<td class="num">{item.samples_present:,} of {item.samples_expected:,}</td>'
            "</tr>"
        )
    return (
        '<section class="section" id="component-list"><h2>Component list</h2><div class="table-wrap"><table>'
        '<caption class="vh">Components in this report</caption><thead><tr>'
        '<th scope="col">Component</th><th scope="col">Layer</th><th scope="col">State</th>'
        '<th scope="col">Dominant</th><th scope="col">Secondary</th><th scope="col">Samples</th>'
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>"
    )


def _details(report: Report, components: list) -> str:
    articles = []
    for item in components:
        facts = "".join(
            f"<div><dt>{_text(fact.label)}</dt><dd class=\"num\">{_text(fact.text)}</dd></div>"
            for fact in item.facts
            if fact.label or fact.text
        )
        stats = f'<dl class="stats">{facts}</dl>' if facts else ""
        charts = "".join(_figure(chart, report) for chart in item.charts)
        share = f'<p class="share">{_text(item.share)}</p>' if item.share else ""
        fresh = (
            f"Window ends {format_pt(report.window_end)} · "
            f"{item.samples_present:,} of {item.samples_expected:,} samples"
        )
        kpis = (
            '<div class="kpis">'
            f'<div class="kpi"><p class="kpi-label">Dominant · latest sample</p><p class="kpi-value"><span class="num">{_text(item.dominant.text)}</span></p><p class="kpi-unit">{_text(item.dominant.label)}</p></div>'
            f'<div class="kpi"><p class="kpi-label">Secondary</p><p class="kpi-value"><span class="num">{_text(item.secondary.text)}</span></p><p class="kpi-unit">{_text(item.secondary.label)}</p></div>'
            f'<div class="kpi"><p class="kpi-label">Also</p><p class="kpi-value"><span class="num">{_text(item.also.text)}</span></p><p class="kpi-unit">{_text(item.also.label)}</p></div>'
            "</div>"
        )
        articles.append(
            f'<article class="detail is-{item.state}" id="{_id(item.id)}">'
            f'<header class="detail-head"><div><p class="kicker">{_text(item.layer)}</p>'
            f"<h3>{_text(item.title)}</h3><p class=\"resource\">{_text(item.resource)} · {_text(item.runtime)}</p></div>"
            f"{_badge(item.state)}</header>{share}{kpis}"
            f'<p class="threshold">{_text(item.reason)}</p>'
            f'<p class="fresh">{_text(fresh)}</p>{stats}{charts}</article>'
        )
    return '<section class="section" id="details"><h2>Component detail</h2>' + "".join(articles) + "</section>"


def _figure(chart: ChartView, report: Report) -> str:
    profile = PROFILES[report.profile]
    if chart.present == 0:
        return (
            '<figure class="chart">'
            f"<figcaption><span>{_text(chart.caption)}</span>"
            f'<span class="num">0 of {chart.expected:,} samples</span></figcaption>'
            '<p class="chart-empty">No samples in this window, so there is nothing to draw. '
            "Empty space would read as zero, and this is missing telemetry.</p>"
            f'<p class="chart-note">{_text(chart.note)}</p></figure>'
        )
    legend = []
    for index, (_key, name) in enumerate(chart.series):
        swatch = "swatch-a" if index == 0 else "swatch-b"
        legend.append(f'<li><span class="swatch {swatch}"></span>{_text(name)}</li>')
    for line in chart.thresholds:
        kind = "swatch-warn" if line["kind"] == "warn" else "swatch-crit"
        legend.append(f'<li><span class="swatch {kind}"></span>{_text(line["name"])}</li>')
    aria = (
        f"{chart.caption}. {profile.span_label.capitalize()} ending {format_pt_long(report.window_end)}. "
        f"{chart.present:,} of {chart.expected:,} samples. "
        "Arrow keys move one bucket. Shift plus arrow moves one hour."
    )
    return (
        '<figure class="chart">'
        f"<figcaption><span>{_text(chart.caption)}</span>"
        f'<span class="num">{chart.present:,} of {chart.expected:,} samples</span></figcaption>'
        f'<p class="readout" aria-live="off">{_text(_readout(chart, report))}</p>'
        f'<div class="plot" tabindex="0" role="img" data-chart="{_id(chart.id)}" aria-label="{_attr(aria)}"></div>'
        f'<ul class="legend">{"".join(legend)}</ul>'
        f'<p class="chart-note">{_text(chart.note)}</p></figure>'
    )


def _readout(chart: ChartView, report: Report) -> str:
    index = report.count - 1
    epoch = report.window_start + index * report.step
    bits = []
    for key, name in chart.series:
        value = report.series[key][index]
        bits.append(f"{name}: {_format_readout(value, chart.fmt)}")
    return f"{format_pt(epoch)} — " + " · ".join(bits) + "."


def _format_readout(value, fmt: str) -> str:
    if value is None:
        return "No sample"
    return format_number(value, fmt)


def _method_items() -> list:
    c = catalog
    return [
        f"SQL and App Service plan CPU and memory: degraded at {c.CPU_WARN:g}%, critical at {c.CPU_CRIT:g}%.",
        (
            f"HTTP queue: degraded at {c.QUEUE_WARN:g}, critical at {c.QUEUE_CRIT:g}. "
            "Windows sites report their own queue. Linux sites (Comvoy, locator) do not, so the App Service plan HttpQueueLength stands in."
        ),
        (
            f"Server errors (5xx): responses with status 500 or higher divided by all requests, over the trailing {c.RATE_WINDOW_MINUTES} minutes. "
            f"Degraded at {c.FAIL_WARN:g}%, critical at {c.FAIL_CRIT:g}%, only when those minutes have at least {c.MIN_REQUESTS:g} requests. "
            "404 and other 4xx responses are not counted. The all-failures figure includes them and is not scored, because bot traffic makes 404s a large share of dealer-site requests. "
            "Counts use sum(itemCount) on the classic requests table, filtered by cloud_RoleName where several services share a component."
        ),
        f"Dealer site average request duration: critical above {c.DEALER_DURATION_CRIT:,.0f} ms. p95 is shown and is not that alert.",
        f"Azure AI Search throttled queries: critical above {c.SEARCH_THROTTLE_CRIT:g}%.",
        "CRM container restarts: any restart in a bucket is critical.",
        "CDC handler failures and CDC Service Bus receive errors: any count above 0 is critical.",
        (
            f"CDC consumer stalled: critical when data-changes received messages and delivered none over {c.CDC_STALL_MINUTES} minutes. "
            "Topic depth is not charted."
        ),
        f"Notification dead letters: degraded above 0. Email scan dead letters: degraded above {c.EMAIL_DLQ_BASELINE:g}.",
        (
            f"Comvoy search-results failure above {c.COMVOY_SRP_FAIL_PCT:g}% for {c.COMVOY_SRP_MINUTES} minutes "
            f"(minimum {c.COMVOY_SRP_MIN_REQUESTS:g} requests) is critical. Volume above {c.COMVOY_SRP_VOLUME:,.0f} in "
            f"{c.COMVOY_SRP_VOLUME_MINUTES} minutes is degraded. SubmitLead failure above {c.COMVOY_LEAD_FAIL_PCT:g}% for "
            f"{c.COMVOY_LEAD_MINUTES} minutes (minimum {c.COMVOY_LEAD_MIN_REQUESTS:g} requests) is critical. "
            "Those lines were read from the scheduled query rules and, like the alerts, count success == false."
        ),
        "WebJobs request reliability stays unknown when Application Insights has too few requests to score. Platform Http5xx is a separate chart.",
        "Exceptions per bucket are shown for the dealer site, Web API, Search API, and Comvoy. They are not scored.",
        "A fresh measurement with no configured threshold stays unknown. It is not marked healthy. Stale or missing data stays unknown.",
        f"Autoscale setting {c.AUTOSCALE_SETTING} is named only. Its rule body is not a threshold.",
    ]


def _mode_paragraph(report: Report) -> str:
    profile = PROFILES[report.profile]
    if profile.live:
        return (
            "<p>This is the live view: one-minute buckets for the last day. A local server queries Azure every minute. "
            "Each refresh re-queries the trailing 30 minutes, keeps earlier buckets from previous queries, and re-queries the whole day hourly. "
            "Azure Monitor trails real time by one to three minutes, so the newest buckets fill in on later refreshes. "
            "This page checks the server every 30 seconds and replaces itself when there is new data.</p>"
        )
    return (
        "<p>This is a snapshot: five-minute buckets for the last seven days, written to one file. "
        "The file is self-contained and makes no requests when opened.</p>"
    )


def _footer(report: Report) -> str:
    quality = report.data_quality or ["No query failures were recorded for this run."]
    quality_items = "".join(f"<li>{_text(item)}</li>" for item in quality)
    queries = sorted(report.queries, key=lambda item: item.name)
    query_rows = []
    for item in queries:
        detail = item.error or item.detail or ""
        query_rows.append(
            "<tr>"
            f"<td>{_text(item.name)}</td>"
            f"<td>{_text(item.status)}</td>"
            f'<td class="num">{item.duration_ms:,}</td>'
            f"<td>{_text(detail)}</td>"
            "</tr>"
        )
    query_table = (
        '<table><caption>Query outcomes for this run</caption><thead><tr>'
        '<th scope="col">Query</th><th scope="col">Status</th><th scope="col">Duration ms</th><th scope="col">Detail</th>'
        f"</tr></thead><tbody>{''.join(query_rows)}</tbody></table>"
        if query_rows
        else ""
    )
    maintenance = f"<p>{_text(report.maintenance_note)}</p>" if report.maintenance_note else ""
    items = "".join(f"<li>{_text(text)}</li>" for text in _method_items())
    return (
        '<footer class="foot"><div class="foot-inner method">'
        "<h2>How this report scores health</h2>"
        f"{_mode_paragraph(report)}"
        f"<p>Headline figures use the latest sample in the last {FRESHNESS_SECONDS // 60} minutes. "
        f"The window ends {iso_utc(report.window_end)}, which is {_text(format_pt(report.window_end))}. "
        "Timestamps in the file are UTC epoch seconds. Labels use America/Los_Angeles. "
        "A missing sample is a gap. The chart does not connect across it.</p>"
        f"<ul>{items}</ul>"
        "<p>Dealer site requests come from Production-DealerSite in wts-prod-40. "
        "The Application Insights component named wts-prod-dealersite in wts-prod is not queried. "
        "Comvoy requests come from wts-prod-searchwebapi under role comvoy-frontend-server; the component named comvoy-frontend-prod-linux receives none.</p>"
        f"{maintenance}"
        "<h2>Data quality</h2>"
        f"<ul>{quality_items}</ul>"
        f"{query_table}"
        f"<p>Schema version {catalog.SCHEMA_VERSION}. "
        + (
            "A later step can upload the dated file and latest.html to Azure Blob Storage. This run does not."
            if not PROFILES[report.profile].live
            else "Nothing is stored between refreshes except the current day held in the server's memory."
        )
        + "</p>"
        "</div></footer>"
    )


def _chart_payload(report: Report) -> dict:
    profile = PROFILES[report.profile]
    charts = {}
    needed = set()
    for component in report.components:
        for chart in component.charts:
            if chart.present == 0:
                continue
            for key, _name in chart.series:
                needed.add(key)
            if chart.volume:
                needed.add(chart.volume)
            charts[chart.id] = {
                "format": chart.fmt,
                "yMax": chart.y_max,
                "ticks": chart.ticks,
                "series": [{"key": key, "name": name} for key, name in chart.series],
                "thresholds": chart.thresholds,
                "bands": [],
                "volume": chart.volume or "",
                "sum": chart.sum_series,
                "note": chart.note,
                "caption": chart.caption,
            }
    series = {key: [_json_number(value) for value in report.series[key]] for key in sorted(needed)}
    layers = {item.id: item.row - 2 for item in report.components if item.on_map}
    stacks = {item.id: item.stack for item in report.components if item.on_map}
    present = {item.id for item in report.components if item.on_map}
    links = [list(edge) for edge in report.edges if edge[0] in present and edge[1] in present]
    return {
        "start": report.window_start,
        "step": report.step,
        "count": report.count,
        "hour": 3600 // report.step,
        "mode": profile.name,
        "series": series,
        "charts": charts,
        "links": links,
        "layers": layers,
        "stacks": stacks,
    }


def _json_number(value):
    from ops_dashboard.format import json_number

    return json_number(value)


def _badge(state: str) -> str:
    label = LABELS.get(state, "Unknown")
    return f'<span class="badge">{badge_svg(state)}{_text(label)}</span>'


def _json(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    return raw.replace("<", "\\u003c")


def _text(value) -> str:
    return escape(str(value), quote=False)


def _attr(value: str) -> str:
    return escape(value, quote=True)


def _id(value: str) -> str:
    if not _ID.fullmatch(value):
        raise ValueError(f"unsafe id {value}")
    return value
