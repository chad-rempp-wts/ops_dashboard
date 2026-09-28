from datetime import datetime, timezone

from ops_dashboard.profile import LIVE, SNAPSHOT
from ops_dashboard.series import failure_rates, rolling_sum
from ops_dashboard.window import window_ending


def test_profiles_fix_bucket_count_and_smoothing():
    assert (SNAPSHOT.count, SNAPSHOT.rate_window, SNAPSHOT.freshness) == (2016, 1, 2)
    assert (LIVE.count, LIVE.rate_window, LIVE.freshness) == (1440, 5, 10)
    assert SNAPSHOT.bucket_label == "five-minute"
    assert LIVE.bucket_label == "one-minute"
    assert LIVE.span_label == "24 hours"
    assert SNAPSHOT.span_label == "seven days"


def test_live_window_is_one_day_ending_on_a_minute():
    now = datetime(2026, 9, 28, 15, 7, 41, tzinfo=timezone.utc)
    start, end = window_ending(None, now, LIVE)
    assert end % 60 == 0
    assert end - start == 86400
    assert end == int(datetime(2026, 9, 28, 15, 7, tzinfo=timezone.utc).timestamp())


def test_catalog_wording_follows_the_bucket_size():
    assert LIVE.localize("Requests / 5 min") == "Requests / min"
    assert SNAPSHOT.localize("Requests / 5 min") == "Requests / 5 min"


def test_rolling_sum_keeps_gaps_and_partial_windows():
    assert rolling_sum([1, 2, 3, 4], 1) == [1, 2, 3, 4]
    assert rolling_sum([1, 2, 3, 4], 3) == [1.0, 3.0, 6.0, 9.0]
    assert rolling_sum([None, None, 2, None], 2) == [None, None, 2.0, 2.0]
    assert rolling_sum([None, None, None], 2) == [None, None, None]


def test_one_minute_rates_are_judged_over_five_minutes():
    totals = [100.0, 100.0, 100.0, 100.0, 100.0, 1.0]
    failed = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    single = failure_rates(totals, failed)
    assert single[-1] == 100.0
    rolled = failure_rates(totals, failed, window=5)
    assert rolled[-1] == round(100.0 * 1 / 401, 4)


def test_rate_gaps_are_not_zero():
    assert failure_rates([None, 0.0], [None, 0.0], window=1) == [None, None]
    rates = failure_rates([10.0, None], [1.0, None], window=2)
    assert rates == [10.0, 10.0]
