"""Align log rows onto the report grid. Empty request bins stay null."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

from report.metrics_parse import parse_timestamp
from report.series import Series, align_map, zero_fill


def _bucket_maps(rows: Iterable[dict], value_fields: Sequence[str]) -> Dict[str, Dict[int, Optional[float]]]:
    maps = {field: {} for field in value_fields}
    for row in rows:
        if row.get("Bucket") is None:
            continue
        timestamp = parse_timestamp(row["Bucket"])
        for field in value_fields:
            raw = row.get(field)
            if raw is None:
                continue
            current = maps[field].get(timestamp)
            if current is None:
                maps[field][timestamp] = float(raw)
            else:
                maps[field][timestamp] = float(current) + float(raw)
    return maps


def request_series(rows: Iterable[dict], start: int, step: int, count: int) -> Dict[str, Series]:
    maps = _bucket_maps(rows, ("Total", "Failed", "AvgMs", "P95Ms"))
    # Duration is not additive. Keep the last observed value when buckets collide.
    for field in ("AvgMs", "P95Ms"):
        collapsed: Dict[int, Optional[float]] = {}
        for row in rows:
            if row.get("Bucket") is None or row.get(field) is None:
                continue
            collapsed[parse_timestamp(row["Bucket"])] = float(row[field])
        maps[field] = collapsed
    return {
        "req": align_map(maps["Total"], start, step, count),
        "failed": align_map(maps["Failed"], start, step, count),
        "avg": align_map(maps["AvgMs"], start, step, count),
        "p95": align_map(maps["P95Ms"], start, step, count),
    }


def operation_series(rows: Iterable[dict], start: int, step: int, count: int) -> Dict[str, Series]:
    grouped = {"srp": [], "lead": []}
    for row in rows:
        kind = str(row.get("Kind") or "")
        target = "lead" if kind == "lead" else "srp"
        grouped[target].append(row)
    result = {}
    for kind, kind_rows in grouped.items():
        maps = _bucket_maps(kind_rows, ("Total", "Failed"))
        prefix = "lead" if kind == "lead" else "srp"
        result[f"{prefix}Req"] = zero_fill(align_map(maps["Total"], start, step, count))
        result[f"{prefix}Fail"] = zero_fill(align_map(maps["Failed"], start, step, count))
    return result


def event_counts(rows: Iterable[dict], field: str, start: int, step: int, count: int) -> List[Optional[float]]:
    maps = _bucket_maps(rows, (field,))
    return zero_fill(align_map(maps[field], start, step, count))
