"""Deterministic offline series for tests and the fixture report."""

from __future__ import annotations

from typing import Dict, List, Optional

from report.build import build_report
from report.catalog import all_series_keys
from report.model import QueryRecord, Report
from report.window import parse_end, window_ending

FIXTURE_END = "2026-09-28T15:00:00Z"


def build_fixture(end_text: str = FIXTURE_END) -> Report:
    start, end = window_ending(parse_end(end_text))
    count = (end - start) // 300
    series = _series(count)
    queries = [
        QueryRecord(
            name="Fixture",
            source="fixture",
            duration_ms=0,
            status="ok",
            detail="Synthetic series. No Azure calls.",
        ),
        QueryRecord(
            name="Fixture escape check",
            source="fixture",
            duration_ms=1,
            status="error",
            error="boom <script>alert(1)</script> & co",
        ),
    ]
    return build_report(
        series,
        start=start,
        end=end,
        generated_epoch=end,
        fixture=True,
        states={"locator": "stopped", "publicapi": "absent"},
        queries=queries,
        data_quality=["Fixture run does not query Azure."],
    )


def _series(count: int) -> Dict[str, List[Optional[float]]]:
    series: Dict[str, List[Optional[float]]] = {}
    for key in all_series_keys():
        series[key] = _baseline(key, count)
    for index in range(100, 115):
        for key in ("dealerReq", "dealerFailCount", "dealerAvg", "dealerP95"):
            series[key][index] = None
    series["dealerReq"][-1] = 2498
    series["dealerFailCount"][-1] = 36.221
    series["sqlCpu"][-1] = 91.4
    series["sqlCpu"][-30] = 95.2
    series["planCpu"][-1] = 74.2
    series["planCpu"][-40] = 77.6
    series["comvoyReq"] = [None] * count
    series["comvoyFailCount"] = [None] * count
    series["comvoyHttp5xx"] = [1.0] * count
    series["webjobsReq"] = [None] * count
    series["webjobsFailCount"] = [None] * count
    for index in range(0, count, 112):
        series["webjobsReq"][index] = 4
    for key in ("fd1Req", "fd2Req"):
        series[key] = [float(1800 + (index % 48) * 20) for index in range(count)]
    series["fd1Req"][-1] = 2764
    series["fd2Req"][-1] = 1815
    return series


def _baseline(key: str, count: int) -> List[Optional[float]]:
    if key.endswith("Req") or key.endswith("FailCount") or key in ("srpReq", "srpFail", "leadReq", "leadFail"):
        if key.endswith("FailCount") or key.endswith("Fail"):
            return [0.0] * count
        return [200.0] * count
    if key.endswith("Cpu") or key.endswith("Mem") or key in ("sqlCpu", "sqlWorkers", "sqlStorage", "sqlDtu", "redisMem"):
        return [22.0] * count
    if "Lat" in key or key.endswith("HttpRt") or key.endswith("Avg") or key.endswith("P95") or key == "searchLatency":
        return [180.0] * count
    if key == "searchThrottle" or key.endswith("P5"):
        return [0.01] * count
    if key in ("signalrConn", "redisClients"):
        return [40.0] * count
    if key in ("cdcIn", "cdcOut"):
        return [5.0] * count
    if key == "emailDlq":
        return [4.0] * count
    if key == "gwTotal":
        return [300.0] * count
    return [0.0] * count
