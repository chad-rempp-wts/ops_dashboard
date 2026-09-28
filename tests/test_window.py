from datetime import datetime, timezone

from report.series import align_map, iter_chunks, merge_timestamp_maps
from report.window import STEP_SECONDS, window_ending


def test_week_splits_into_seven_exact_days():
    start, end = window_ending(1_700_000_000)
    chunks = list(iter_chunks(start, end, 86400))
    assert len(chunks) == 7
    assert chunks[0][0] == start
    assert chunks[-1][1] == end
    assert all(right - left == 86400 for left, right in chunks)
    assert all(left_end == right_start for (_a, left_end), (right_start, _b) in zip(chunks, chunks[1:]))
    assert (end - start) // STEP_SECONDS == 2016
    assert 86400 // STEP_SECONDS == 288


def test_chunk_boundary_keeps_one_sample_and_prefers_a_value_over_null():
    merged = merge_timestamp_maps(
        [
            {100: 1.0, 200: None},
            {200: 5.0, 300: 3.0},
            {100: 9.0, 300: None},
        ]
    )
    assert merged[100] == 1.0
    assert merged[200] == 5.0
    assert merged[300] == 3.0


def test_align_leaves_gaps_and_does_not_interpolate():
    aligned = align_map({0: 1.0, 600: 3.0}, start=0, step=300, count=4)
    assert aligned == [1.0, None, 3.0, None]


def test_window_ends_on_a_five_minute_boundary():
    moment = datetime(2026, 9, 28, 18, 32, 10, tzinfo=timezone.utc)
    start, end = window_ending(now=moment)
    assert end == int(datetime(2026, 9, 28, 18, 30, tzinfo=timezone.utc).timestamp())
    assert end - start == 2016 * 300
    assert end % 300 == 0
