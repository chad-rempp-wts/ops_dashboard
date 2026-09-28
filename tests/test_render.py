import json
import re

from report.fixture import build_fixture
from report.icons import LABELS, badge_svg
from report.render import render_html
from report.window import BUCKETS_PER_WEEK


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
    assert states["comvoy"] == "unknown"
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
