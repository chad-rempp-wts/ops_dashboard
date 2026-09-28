from report.format import format_number
from report.health import evaluate_stall, evaluate_threshold, freshest_index, rollup


def _fmt(fmt):
    return lambda value: format_number(value, fmt)


def test_missing_sample_is_unknown_not_healthy():
    values = [10.0] + [None] * 2015
    verdict = evaluate_threshold(
        values,
        metric="sqlCpu",
        noun="CPU",
        warning=70,
        critical=85,
        op="gte",
        format_value=_fmt("pct1"),
        start=0,
        step=300,
    )
    assert verdict.state == "unknown"
    assert freshest_index(values) is None


def test_low_volume_failure_rate_is_unknown():
    verdict = evaluate_threshold(
        [0.0] * 2016,
        metric="dealerRate",
        noun="Failed requests",
        warning=1,
        critical=3,
        op="gte",
        format_value=_fmt("pct2"),
        start=0,
        step=300,
        volume=[10.0] * 2016,
        min_volume=50,
    )
    assert verdict.state == "unknown"


def test_threshold_direction_and_bounds():
    common = dict(
        metric="sqlCpu",
        noun="CPU",
        warning=70,
        critical=85,
        op="gte",
        format_value=_fmt("pct1"),
        start=0,
        step=300,
    )
    assert evaluate_threshold([69.9], **common).state == "healthy"
    assert evaluate_threshold([70.0], **common).state == "degraded"
    assert evaluate_threshold([85.0], **common).state == "critical"

    duration = evaluate_threshold(
        [2000.0],
        metric="dealerAvg",
        noun="Average request duration",
        warning=None,
        critical=2000,
        op="gt",
        format_value=_fmt("ms"),
        start=0,
        step=300,
    )
    assert duration.state == "healthy"
    over = evaluate_threshold(
        [2000.1],
        metric="dealerAvg",
        noun="Average request duration",
        warning=None,
        critical=2000,
        op="gt",
        format_value=_fmt("ms"),
        start=0,
        step=300,
    )
    assert over.state == "critical"


def test_volume_guard_allows_a_real_rate_to_score():
    verdict = evaluate_threshold(
        [1.5],
        metric="dealerRate",
        noun="Failed requests",
        warning=1,
        critical=3,
        op="gte",
        format_value=_fmt("pct2"),
        start=0,
        step=300,
        volume=[200.0],
        min_volume=50,
    )
    assert verdict.state == "degraded"


def test_unknown_outranks_healthy_and_critical_outranks_unknown():
    unknown = evaluate_threshold(
        [None],
        metric="a",
        noun="A",
        warning=1,
        critical=3,
        op="gte",
        format_value=_fmt("pct1"),
        start=0,
        step=300,
    )
    healthy = evaluate_threshold(
        [0.1],
        metric="b",
        noun="B",
        warning=1,
        critical=3,
        op="gte",
        format_value=_fmt("pct1"),
        start=0,
        step=300,
    )
    critical = evaluate_threshold(
        [90.0],
        metric="c",
        noun="C",
        warning=70,
        critical=85,
        op="gte",
        format_value=_fmt("pct1"),
        start=0,
        step=300,
    )
    assert rollup([healthy, unknown]).state == "unknown"
    assert rollup([unknown, critical]).state == "critical"


def test_cdc_stall_requires_fifteen_quiet_minutes_of_delivery():
    stalled = evaluate_stall([2, 2, 2], [0, 0, 0], buckets=3, start=0, step=300)
    assert stalled.state == "critical"
    moving = evaluate_stall([2, 2, 2], [0, 0, 1], buckets=3, start=0, step=300)
    assert moving.state == "healthy"
    gap = evaluate_stall([2, None, 2], [0, 0, 0], buckets=3, start=0, step=300)
    assert gap.state == "unknown"
