import json
import re

from ops_dashboard.fixture import build_fixture
from ops_dashboard.icons import LABELS, badge_svg
from ops_dashboard.profile import LIVE
from ops_dashboard.render import render_html
from ops_dashboard.window import BUCKETS_PER_WEEK


def test_fixture_series_are_a_full_week():
    report = build_fixture()
    assert report.count == BUCKETS_PER_WEEK == 2016
    assert report.series
    for key, values in report.series.items():
        assert len(values) == 2016, key
    html = render_html(report)
    payload = json.loads(_report_json(html))
    assert payload["count"] == 2016
    assert payload["step"] == 300
    for key, values in payload["series"].items():
        assert len(values) == 2016, key


def test_fixture_health_matches_the_rules():
    report = build_fixture()
    states = {item.id: item.state for item in report.components}
    assert states["sql"] == "critical"
    assert states["dealer"] == "degraded"
    assert states["plan"] == "degraded"
    assert states["comvoy"] == "healthy"
    assert states["webjobs"] == "unknown"
    assert states["locator"] == "unknown"
    assert states["fd"] == "unknown"
    assert states["signalr"] == "unknown"
    assert states["redis"] == "unknown"
    assert states["tracker"] == "maintenance"
    assert states["webapi"] == "healthy"
    assert "publicapi" not in states
    assert report.absent_notes


def test_html_is_standalone_and_escapes_telemetry():
    html = render_html(build_fixture())
    assert "http://" not in html.lower()
    assert "https://" not in html.lower()
    assert "url(" not in html.lower()
    assert "fetch(" not in html.lower()
    assert "xmlhttprequest" not in html.lower()
    assert "live-pill\"" not in html
    assert 'data-mode="snapshot"' in html
    assert "@import" not in html.lower()
    assert re.search(r"\bsrc\s*=", html, re.I) is None
    assert re.search(r"""href\s*=\s*["'](?!#)""", html) is None
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "alert(1)" in html
    assert 'id="report-data"' in html
    assert 'id="links"' in html
    assert "is-critical" in html
    assert "is-unknown" in html
    assert "is-maintenance" in html
    assert ">Critical<" in html
    assert ">Unknown<" in html
    assert ">Maintenance<" in html
    assert ">Healthy<" in html
    assert ">Degraded<" in html


def test_badges_use_word_symbol_and_distinct_markup():
    for state, word in (
        ("healthy", "Healthy"),
        ("degraded", "Degraded"),
        ("critical", "Critical"),
        ("maintenance", "Maintenance"),
        ("unknown", "Unknown"),
    ):
        markup = badge_svg(state)
        assert LABELS[state] == word
        assert "<path" in markup
        assert "http" not in markup


def _report_json(html: str) -> str:
    start = html.find('<script type="application/json" id="report-data">')
    start = html.find(">", start) + 1
    end = html.find("</script>", start)
    return html[start:end]


def test_live_fixture_is_one_day_of_minutes():
    report = build_fixture(profile=LIVE)
    assert report.profile == "live"
    assert report.count == 1440
    assert report.step == 60
    for key, values in report.series.items():
        assert len(values) == 1440, key
    html = render_html(report, live=True, version="7")
    payload = json.loads(_report_json(html))
    assert payload["count"] == 1440
    assert payload["hour"] == 60
    assert 'id="live-pill"' in html
    assert 'data-version="7"' in html
    assert 'id="app"' in html
    assert "one-minute buckets" in html
    assert "Seven days" not in html


def test_live_health_matches_snapshot_for_the_same_conditions():
    snapshot = {item.id: item.state for item in build_fixture().components}
    live = {item.id: item.state for item in build_fixture(profile=LIVE).components}
    assert live == snapshot


def test_scoring_is_on_5xx_and_all_failures_are_shown_unscored():
    report = build_fixture()
    dealer = next(item for item in report.components if item.id == "dealer")
    labels = [fact.label for fact in dealer.facts]
    assert any("not scored" in label for label in labels)
    html = render_html(report)
    assert "Server errors (5xx)" in html
    assert "404 and other 4xx responses are not counted" in html


def test_snapshot_methodology_comes_from_the_catalog():
    from ops_dashboard import catalog

    html = render_html(build_fixture())
    assert f"Degraded at {catalog.FAIL_WARN:g}%, critical at {catalog.FAIL_CRIT:g}%" in html
    assert f"{catalog.CDC_STALL_MINUTES} minutes" in html


def test_a_chart_with_no_samples_says_so_instead_of_drawing_nothing():
    from ops_dashboard.model import ChartView
    from ops_dashboard.render import _figure

    report = build_fixture()
    chart = ChartView("empty-chart", "Requests", "int", 10.0, [0.0, 10.0], [("webjobsReq", "Requests")], [], None, False, "note", 0, 2016)
    markup = _figure(chart, report)
    assert "chart-empty" in markup
    assert "No samples in this window" in markup
    assert "data-chart" not in markup
