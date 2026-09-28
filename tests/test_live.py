from ops_dashboard.collect import Collected
from ops_dashboard.live import TAIL_SECONDS, LiveEngine, _merge_tail, _rolled
from ops_dashboard.model import QueryRecord
from ops_dashboard.profile import LIVE

NOW = 1_790_000_040.0  # divisible by 60


class Clock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


class FakeCollector:
    """Returns a dealer request count that equals the bucket's epoch minute, so rolling is checkable."""

    def __init__(self):
        self.calls = []
        self.fail = False

    def collect(self, start, end):
        self.calls.append((start, end))
        if self.fail:
            raise RuntimeError("azure said no\nsecond line")
        count = (end - start) // 60
        values = [float((start + i * 60) // 60) for i in range(count)]
        return Collected(
            {"dealerReq": values},
            {},
            [QueryRecord("fake", "log", 1, "ok")],
            [],
            set(),
        )


def _engine(clock=None):
    collector = FakeCollector()
    clock = clock or Clock(NOW)
    return LiveEngine(collector, clock=clock), collector, clock


def test_first_refresh_queries_the_whole_day():
    engine, collector, _ = _engine()
    assert engine.current() is None
    engine.refresh()
    start, end = collector.calls[0]
    assert end - start == 86400
    current = engine.current()
    assert current.report.profile == "live"
    assert current.report.count == 1440
    assert current.status["ok"] is True
    assert current.version == str(int(NOW))


def test_later_refresh_requeries_only_the_tail_and_rolls_the_window():
    engine, collector, clock = _engine()
    engine.refresh()
    clock.value = NOW + 180
    engine.refresh()
    start, end = collector.calls[1]
    assert end - start == TAIL_SECONDS
    dealer = engine.current().report.series["dealerReq"]
    assert len(dealer) == 1440
    window_start = engine.current().report.window_start
    for index in (0, 700, 1439):
        assert dealer[index] == float((window_start + index * 60) // 60)
    assert engine.status()["tail_runs"] == 1
    assert engine.status()["full_runs"] == 1


def test_a_full_requery_runs_after_an_hour():
    engine, collector, clock = _engine()
    engine.refresh()
    clock.value = NOW + 3700
    engine.refresh()
    assert collector.calls[1][1] - collector.calls[1][0] == 86400
    assert engine.status()["full_runs"] == 2


def test_failure_keeps_the_last_good_report_and_says_why():
    engine, collector, clock = _engine()
    engine.refresh()
    before = engine.current()
    collector.fail = True
    clock.value = NOW + 60
    engine.refresh()
    after = engine.current()
    assert after.report is before.report
    assert after.version == before.version
    assert after.status["ok"] is False
    assert after.status["error"] == "azure said no"
    collector.fail = False
    clock.value = NOW + 120
    engine.refresh()
    assert engine.status()["ok"] is True
    assert engine.status()["error"] is None


def test_roll_and_merge_helpers():
    assert _rolled({"a": [1, 2, 3]}, 1, 3) == {"a": [2, 3, None]}
    assert _rolled({"a": [1, 2, 3]}, 0, 3) == {"a": [1, 2, 3]}
    series = {"a": [1, 2, 3, 4]}
    _merge_tail(series, {"a": [9, None], "b": [5, 6]}, 1, 4)
    assert series["a"] == [1, 9, 3, 4]
    assert series["b"] == [None, 5, 6, None]


def test_live_step_is_one_minute():
    assert LIVE.step == 60
