"""Kusto text for Application Insights and Log Analytics. Names come from the catalog."""

from __future__ import annotations

import re
from typing import Optional

from ops_dashboard.window import iso_utc

_ROLE = re.compile(r"^[A-Za-z0-9._-]+$")


def _window(start: int, end: int) -> str:
    return (
        f"let windowStart = datetime({iso_utc(start)});\n"
        f"let windowEnd = datetime({iso_utc(end)});\n"
    )


def _span(step: int) -> str:
    """Kusto timespan literal for a bucket size in seconds."""
    if step % 60:
        raise ValueError("bucket size must be a whole number of minutes")
    return f"{step // 60}m"


def _role_filter(role: Optional[str]) -> str:
    """Several services report into one component. Names come from the catalog, never from telemetry."""
    if not role:
        return ""
    if not _ROLE.fullmatch(role):
        raise ValueError(f"unsafe role name {role}")
    return f'| where cloud_RoleName == "{role}"\n'


def requests_kql(start: int, end: int, step: int = 300, role: Optional[str] = None) -> str:
    """Classic requests table. Counts use sum(itemCount). Empty bins stay null via a left join.

    Failed is server errors only (resultCode >= 500). FailedAll is everything marked
    success == false, which includes 404s from bots. Only Failed is scored.
    """
    span = _span(step)
    return (
        _window(start, end)
        + f"let grid = range Bucket from windowStart to windowEnd - {span} step {span}\n"
        "| project Bucket;\n"
        "let agg = requests\n"
        "| where timestamp >= windowStart and timestamp < windowEnd\n"
        + _role_filter(role)
        + "| summarize Total = sum(itemCount), "
        "Failed = sumif(itemCount, toint(resultCode) >= 500), "
        "FailedAll = sumif(itemCount, success == false), "
        f"AvgMs = avg(duration), P95Ms = percentile(duration, 95) by Bucket = bin(timestamp, {span});\n"
        "grid\n"
        "| join kind=leftouter (agg) on Bucket\n"
        "| project Bucket, Total, Failed, FailedAll, AvgMs, P95Ms\n"
        "| order by Bucket asc\n"
    )


def exceptions_kql(start: int, end: int, step: int = 300, role: Optional[str] = None) -> str:
    span = _span(step)
    return (
        _window(start, end)
        + "exceptions\n"
        "| where timestamp >= windowStart and timestamp < windowEnd\n"
        + _role_filter(role)
        + f"| summarize Count = sum(itemCount) by Bucket = bin(timestamp, {span})\n"
        "| project Bucket, Count\n"
        "| order by Bucket asc\n"
    )


def comvoy_ops_kql(start: int, end: int, step: int = 300) -> str:
    """Mirrors the Comvoy scheduled-query alert rules, which match on request name and success."""
    span = _span(step)
    return (
        _window(start, end)
        + "requests\n"
        "| where timestamp >= windowStart and timestamp < windowEnd\n"
        '| where name has "ComvoySearchResultsPage" or name has "SubmitLead"\n'
        '| extend Kind = iff(name has "SubmitLead", "lead", "srp")\n'
        "| summarize Total = sum(itemCount), Failed = sumif(itemCount, success == false) "
        f"by Bucket = bin(timestamp, {span}), Kind\n"
        "| project Bucket, Kind, Total, Failed\n"
        "| order by Bucket asc\n"
    )


def cdc_handler_kql(start: int, end: int, step: int = 300) -> str:
    span = _span(step)
    return (
        _window(start, end)
        + "ContainerAppConsoleLogs_CL\n"
        '| where TimeGenerated >= windowStart and TimeGenerated < windowEnd\n'
        '| where ContainerAppName_s == "wtscrm-api-prod"\n'
        '| where Log_s has "CDC: Unhandled error processing" or Log_s has "CDC: Handler error" '
        'or Log_s has "CDC: Failed to process message"\n'
        f"| summarize failures = count() by Bucket = bin(TimeGenerated, {span})\n"
        "| project Bucket, failures\n"
        "| order by Bucket asc\n"
    )


def cdc_servicebus_kql(start: int, end: int, step: int = 300) -> str:
    span = _span(step)
    return (
        _window(start, end)
        + "ContainerAppConsoleLogs_CL\n"
        "| where TimeGenerated >= windowStart and TimeGenerated < windowEnd\n"
        '| where ContainerAppName_s == "wtscrm-api-prod"\n'
        '| where Log_s has "CDC: Service Bus error"\n'
        f"| summarize errors = count() by Bucket = bin(TimeGenerated, {span})\n"
        "| project Bucket, errors\n"
        "| order by Bucket asc\n"
    )


def kql_for(kind: str, start: int, end: int, step: int = 300, role: Optional[str] = None) -> str:
    if kind == "requests":
        return requests_kql(start, end, step, role)
    if kind == "exceptions":
        return exceptions_kql(start, end, step, role)
    if kind == "comvoy_ops":
        return comvoy_ops_kql(start, end, step)
    if kind == "cdc_handler":
        return cdc_handler_kql(start, end, step)
    if kind == "cdc_sb":
        return cdc_servicebus_kql(start, end, step)
    raise ValueError(kind)
