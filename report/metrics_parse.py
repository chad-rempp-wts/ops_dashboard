"""Parse Azure Monitor metric payloads. Only the requested aggregation is read."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

from report.series import PointMap

_FIELDS = {
    "Average": "average",
    "Total": "total",
    "Maximum": "maximum",
    "Minimum": "minimum",
    "Count": "count",
}


def parse_timestamp(value) -> int:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp())
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def parse_metric_payload(payload: dict, aggregation: str) -> Dict[str, PointMap]:
    """Return metric name to timestamp map.

    A null requested aggregation stays null even when another aggregation is filled.
    Total sums extra dimension series. Other aggregations keep the max.
    """
    field = _FIELDS[aggregation]
    parsed: Dict[str, PointMap] = {}
    for metric in payload.get("value", []):
        name = (metric.get("name") or {}).get("value")
        if not name:
            continue
        points: PointMap = {}
        for time_series in metric.get("timeseries", []):
            for row in time_series.get("data", []):
                if "timeStamp" not in row:
                    continue
                timestamp = parse_timestamp(row["timeStamp"])
                raw = row.get(field)
                value = None if raw is None else float(raw)
                current = points.get(timestamp, None)
                if timestamp not in points or current is None:
                    points[timestamp] = value
                elif value is not None and aggregation == "Total":
                    points[timestamp] = float(current) + value
                elif value is not None:
                    points[timestamp] = max(float(current), value)
        parsed[name] = points
    return parsed


def supported_metric_names(payload: dict) -> Dict[str, str]:
    """Metric definition name to unit."""
    found = {}
    for item in payload.get("value", []):
        name = (item.get("name") or {}).get("value")
        if name:
            found[name] = str(item.get("unit") or "")
    return found
