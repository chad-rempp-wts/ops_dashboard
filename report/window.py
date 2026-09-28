"""Report window. Display times are America/Los_Angeles. Data timestamps are UTC epochs."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

STEP_SECONDS = 300
BUCKETS_PER_WEEK = 7 * 24 * 12  # 2016
DAY_SECONDS = 86400
PACIFIC = ZoneInfo("America/Los_Angeles")

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def floor_step(epoch: int, step: int = STEP_SECONDS) -> int:
    return epoch - (epoch % step)


def parse_end(text: str) -> int:
    """Parse an ISO-8601 instant. Naive values are treated as UTC."""
    stamp = text.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(stamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def window_ending(end_epoch: int | None = None, now: datetime | None = None) -> tuple[int, int]:
    """Return [start, end) ending at the latest completed five-minute boundary."""
    if end_epoch is None:
        moment = now if now is not None else datetime.now(timezone.utc)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        end_epoch = floor_step(int(moment.timestamp()))
    else:
        end_epoch = floor_step(int(end_epoch))
    start = end_epoch - BUCKETS_PER_WEEK * STEP_SECONDS
    return start, end_epoch


def iso_utc(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_pt(epoch: int) -> str:
    moment = datetime.fromtimestamp(epoch, PACIFIC)
    weekday = _WEEKDAYS[moment.weekday()]
    month = _MONTHS[moment.month - 1]
    return f"{weekday} {month} {moment.day}, {moment.hour:02d}:{moment.minute:02d} PT"


def format_pt_date(epoch: int) -> str:
    moment = datetime.fromtimestamp(epoch, PACIFIC)
    return f"{moment.year:04d}-{moment.month:02d}-{moment.day:02d}"


def format_pt_long(epoch: int) -> str:
    moment = datetime.fromtimestamp(epoch, PACIFIC)
    month = (
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    )[moment.month - 1]
    hour = moment.hour % 12 or 12
    suffix = "AM" if moment.hour < 12 else "PM"
    return f"{month} {moment.day}, {moment.year} at {hour}:{moment.minute:02d} {suffix} Pacific"
