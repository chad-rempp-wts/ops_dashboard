"""Rolling one-day window for live mode.

The first refresh queries the whole day. Later refreshes re-query only the trailing
half hour, roll the window forward one bucket per minute, and overwrite the buckets
they cover. A full re-query runs hourly so late-arriving data cannot drift.

A failed refresh keeps the last good report and records why, so the page can say it is stale.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from ops_dashboard.build import build_report
from ops_dashboard.model import Report
from ops_dashboard.profile import LIVE
from ops_dashboard.render import Parts, render_parts
from ops_dashboard.window import iso_utc, window_ending

logger = logging.getLogger(__name__)

TAIL_SECONDS = 30 * 60
FULL_REFRESH_SECONDS = 60 * 60


@dataclass(frozen=True)
class Current:
    report: Report
    parts: Parts
    version: str
    status: dict


class LiveEngine:
    def __init__(self, collector, clock: Callable[[], float] = time.time) -> None:
        self._collector = collector
        self._clock = clock
        self._lock = threading.Lock()
        self._series: Optional[Dict[str, list]] = None
        self._start = 0
        self._end = 0
        self._last_full = 0.0
        self._current: Optional[Current] = None
        self._error: Optional[str] = None
        self._attempted_at: Optional[float] = None
        self._succeeded_at: Optional[float] = None
        self._query_errors = 0
        self._full_runs = 0
        self._tail_runs = 0

    # -- reads -----------------------------------------------------------------------------

    def current(self) -> Optional[Current]:
        with self._lock:
            if self._current is None:
                return None
            return Current(self._current.report, self._current.parts, self._current.version, self._status_locked())

    def status(self) -> dict:
        with self._lock:
            return self._status_locked()

    def _status_locked(self) -> dict:
        return {
            "ready": self._current is not None,
            "ok": self._error is None and self._current is not None,
            "error": self._error,
            "refreshed_at": None if self._succeeded_at is None else int(self._succeeded_at),
            "attempted_at": None if self._attempted_at is None else int(self._attempted_at),
            "query_errors": self._query_errors,
            "full_runs": self._full_runs,
            "tail_runs": self._tail_runs,
        }

    # -- refresh ---------------------------------------------------------------------------

    def refresh(self) -> None:
        """Never raises. A failure is recorded and the previous report stays in place."""
        now = self._clock()
        with self._lock:
            self._attempted_at = now
        try:
            self._refresh(now)
        except Exception as exc:  # noqa: BLE001 - the server must outlive any Azure failure
            message = str(exc).splitlines()[0][:240] if str(exc) else exc.__class__.__name__
            logger.warning("live refresh failed: %s", message)
            with self._lock:
                self._error = message

    def _refresh(self, now: float) -> None:
        profile = LIVE
        step = profile.step
        start, end = window_ending(None, datetime.fromtimestamp(now, timezone.utc), profile)
        count = (end - start) // step
        shift = (end - self._end) // step if self._series is not None else 0
        full = (
            self._series is None
            or now - self._last_full >= FULL_REFRESH_SECONDS
            or shift < 0
            or shift >= count // 2
        )
        if full:
            result = self._collector.collect(start, end)
            series = {key: list(values) for key, values in result.series.items()}
        else:
            tail_start = max(start, end - TAIL_SECONDS)
            result = self._collector.collect(tail_start, end)
            series = _rolled(self._series, shift, count)
            _merge_tail(series, result.series, (tail_start - start) // step, count)
        report = build_report(
            series,
            start=start,
            end=end,
            generated_epoch=int(now),
            fixture=False,
            profile=profile,
            states=result.states,
            queries=result.queries,
            data_quality=result.quality,
            unavailable=result.unavailable,
        )
        parts = render_parts(report)
        query_errors = sum(1 for item in result.queries if item.status == "error")
        with self._lock:
            self._series = series
            self._start, self._end = start, end
            if full:
                self._last_full = now
                self._full_runs += 1
            else:
                self._tail_runs += 1
            self._succeeded_at = now
            self._error = None
            self._query_errors = query_errors
            self._current = Current(report, parts, str(int(now)), {})


class FixtureEngine:
    """Same interface as LiveEngine with synthetic data, so the page can be developed offline."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._current: Optional[Current] = None
        self._at: Optional[float] = None

    def current(self) -> Optional[Current]:
        with self._lock:
            if self._current is None:
                return None
            return Current(self._current.report, self._current.parts, self._current.version, self._status_locked())

    def status(self) -> dict:
        with self._lock:
            return self._status_locked()

    def _status_locked(self) -> dict:
        return {
            "ready": self._current is not None,
            "ok": True,
            "error": None,
            "refreshed_at": None if self._at is None else int(self._at),
            "attempted_at": None if self._at is None else int(self._at),
            "query_errors": 0,
            "full_runs": 0,
            "tail_runs": 0,
        }

    def refresh(self) -> None:
        from ops_dashboard.fixture import build_fixture

        now = self._clock()
        _start, end = window_ending(None, datetime.fromtimestamp(now, timezone.utc), LIVE)
        report = build_fixture(iso_utc(end), profile=LIVE)
        parts = render_parts(report)
        with self._lock:
            self._at = now
            self._current = Current(report, parts, str(int(now)), {})


def _rolled(series: Dict[str, list], shift: int, count: int) -> Dict[str, list]:
    """Slide every series left by `shift` buckets, so the day keeps ending at the newest bucket."""
    rolled: Dict[str, list] = {}
    for key, values in series.items():
        if shift <= 0:
            rolled[key] = list(values)
        else:
            rolled[key] = list(values[shift:]) + [None] * shift
    return rolled


def _merge_tail(series: Dict[str, list], tail: Dict[str, list], offset: int, count: int) -> None:
    """A fresh value replaces the old one. A missing fresh value never erases a good one."""
    for key, values in tail.items():
        target: List = series.setdefault(key, [None] * count)
        for index, value in enumerate(values):
            position = offset + index
            if value is not None and 0 <= position < count:
                target[position] = value
