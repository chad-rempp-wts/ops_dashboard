from ops_dashboard.logs_parse import request_series
from ops_dashboard.series import aggregate_request_buckets, failure_rates


def test_sampled_counts_sum_item_count_not_rows():
    totals, failed = aggregate_request_buckets(
        [
            (0, 10, False),
            (0, 5, True),
            (300, 2, False),
        ],
        start=0,
        step=300,
        count=3,
    )
    assert totals == [15.0, 2.0, None]
    assert failed == [10.0, 2.0, None]
    assert failure_rates(totals, failed) == [round(100.0 * 10 / 15, 4), 100.0, None]


def test_zero_requests_are_a_gap_not_a_zero_failure_rate():
    assert failure_rates([0.0, None, 50.0], [0.0, None, 1.0])[0] is None
    assert failure_rates([0.0, None, 50.0], [0.0, None, 1.0])[1] is None
    assert failure_rates([0.0, None, 50.0], [0.0, None, 1.0])[2] == 2.0


def test_request_rows_keep_missing_bins_null():
    parsed = request_series(
        [
            {"Bucket": "1970-01-01T00:00:00Z", "Total": 10, "Failed": 1, "AvgMs": 20, "P95Ms": 40},
            {"Bucket": "1970-01-01T00:10:00Z", "Total": 4, "Failed": 0, "AvgMs": 11, "P95Ms": 12},
        ],
        start=0,
        step=300,
        count=4,
    )
    assert parsed["req"] == [10.0, None, 4.0, None]
    assert parsed["failed"][1] is None
    assert failure_rates(parsed["req"], parsed["failed"])[1] is None
