"""Time grids, chunk assembly, and sampled request counts.

Azure Monitor weeks are queried in day-sized pieces. Chunk edges can repeat a
bucket; those timestamps collapse to one sample. Empty buckets stay None.
Nothing in this module fills a gap from its neighbors.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

PointMap = Dict[int, Optional[float]]
Series = List[Optional[float]]


def iter_chunks(start: int, end: int, chunk_seconds: int = 86400) -> Iterable[Tuple[int, int]]:
    """Half-open slices [start, end) of at most chunk_seconds."""
    if chunk_seconds <= 0:
        raise ValueError("chunk_seconds must be positive")
    if end < start:
        raise ValueError("end before start")
    cursor = start
    while cursor < end:
        nxt = min(cursor + chunk_seconds, end)
        yield cursor, nxt
        cursor = nxt


def merge_timestamp_maps(chunks: Sequence[Mapping[int, Optional[float]]]) -> PointMap:
    """Collapse chunk boundaries. A later null does not erase a value."""
    merged: PointMap = {}
    for chunk in chunks:
        for timestamp, value in chunk.items():
            if timestamp not in merged or merged[timestamp] is None:
                merged[timestamp] = value
    return merged


def index_for(timestamp: int, start: int, step: int, count: int) -> Optional[int]:
    """Bucket index. Timestamps within two seconds of a boundary snap to it."""
    if step <= 0 or count <= 0:
        raise ValueError("step and count must be positive")
    delta = timestamp - start
    if delta < -2 or delta >= count * step + 2:
        return None
    nearest = int(round(delta / step))
    if nearest < 0 or nearest >= count:
        return None
    if abs(delta - nearest * step) > 2:
        return None
    return nearest


def align_map(points: Mapping[int, Optional[float]], start: int, step: int, count: int) -> Series:
    """Place samples on the grid. Missing buckets stay None. No interpolation."""
    aligned: Series = [None] * count
    for timestamp, value in points.items():
        index = index_for(int(timestamp), start, step, count)
        if index is None or value is None:
            continue
        if aligned[index] is None:
            aligned[index] = float(value)
    return aligned


def rolling_sum(values: Sequence[Optional[float]], window: int) -> Series:
    """Sum of the present values in the trailing window. All-missing stays missing.

    With window 1 this is the series itself. Buckets before the window fills sum what exists.
    """
    if window <= 1:
        return list(values)
    result: Series = []
    for index in range(len(values)):
        chunk = [value for value in values[max(0, index - window + 1) : index + 1] if value is not None]
        result.append(float(sum(chunk)) if chunk else None)
    return result


def failure_rates(
    totals: Sequence[Optional[float]],
    failed: Sequence[Optional[float]],
    window: int = 1,
) -> Series:
    """Percent failed from sampled counts. A window with no requests is a gap, not zero.

    window > 1 judges each bucket over the trailing window, so a one-minute bucket with
    three requests does not swing the rate on its own.
    """
    if len(totals) != len(failed):
        raise ValueError("totals and failed must be the same length")
    total_sums = rolling_sum(totals, window)
    failed_sums = rolling_sum([0.0 if t is not None and f is None else f for t, f in zip(totals, failed)], window)
    rates: Series = []
    for total, fail in zip(total_sums, failed_sums):
        if total is None or total <= 0:
            rates.append(None)
            continue
        rates.append(round(100.0 * float(fail or 0.0) / float(total), 4))
    return rates


def aggregate_request_buckets(
    events: Sequence[Tuple[int, float, bool]],
    start: int,
    step: int,
    count: int,
) -> Tuple[Series, Series]:
    """Sum itemCount into buckets. Counts are sampled itemCount values, not row counts.

    events are (epoch_seconds, item_count, success). Buckets with no events are None.
    """
    totals: Series = [None] * count
    failed: Series = [None] * count
    for timestamp, item_count, success in events:
        index = index_for(int(timestamp), start, step, count)
        if index is None:
            continue
        if totals[index] is None:
            totals[index] = 0.0
            failed[index] = 0.0
        totals[index] = float(totals[index]) + float(item_count)
        if not success:
            failed[index] = float(failed[index]) + float(item_count)
    return totals, failed


def zero_fill(values: Series) -> Series:
    """Event-count series: a missing bucket after a successful query means zero events."""
    return [0.0 if value is None else float(value) for value in values]


def trailing_sum(values: Sequence[Optional[float]], buckets: int) -> Optional[float]:
    """Sum of the last N buckets. Any gap makes the window unknown."""
    if buckets <= 0 or len(values) < buckets:
        return None
    window = list(values[-buckets:])
    if any(value is None for value in window):
        return None
    return float(sum(value for value in window if value is not None))


def count_present(values: Sequence[Optional[float]]) -> int:
    return sum(1 for value in values if value is not None)
