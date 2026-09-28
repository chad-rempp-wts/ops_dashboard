"""Kusto text for Application Insights and Log Analytics. Names come from the catalog."""

from __future__ import annotations

from report.window import iso_utc


def _window(start: int, end: int) -> str:
    return (
        f"let windowStart = datetime({iso_utc(start)});\n"
        f"let windowEnd = datetime({iso_utc(end)});\n"
    )


def requests_kql(start: int, end: int) -> str:
    """Classic requests table. Counts use sum(itemCount). Empty bins stay null via a left join."""
    return (
        _window(start, end)
        + "let grid = range Bucket from windowStart to windowEnd - 5m step 5m\n"
        "| project Bucket;\n"
        "let agg = requests\n"
        "| where timestamp >= windowStart and timestamp < windowEnd\n"
        "| summarize Total = sum(itemCount), Failed = sumif(itemCount, success == false), "
        "AvgMs = avg(duration), P95Ms = percentile(duration, 95) by Bucket = bin(timestamp, 5m);\n"
        "grid\n"
        "| join kind=leftouter (agg) on Bucket\n"
        "| project Bucket, Total, Failed, AvgMs, P95Ms\n"
        "| order by Bucket asc\n"
    )


def comvoy_ops_kql(start: int, end: int) -> str:
    return (
        _window(start, end)
        + "requests\n"
        "| where timestamp >= windowStart and timestamp < windowEnd\n"
        '| where name has "ComvoySearchResultsPage" or name has "SubmitLead"\n'
        '| extend Kind = iff(name has "SubmitLead", "lead", "srp")\n'
        "| summarize Total = sum(itemCount), Failed = sumif(itemCount, success == false) "
        "by Bucket = bin(timestamp, 5m), Kind\n"
        "| project Bucket, Kind, Total, Failed\n"
        "| order by Bucket asc\n"
    )


def cdc_handler_kql(start: int, end: int) -> str:
    return (
        _window(start, end)
        + "ContainerAppConsoleLogs_CL\n"
        '| where TimeGenerated >= windowStart and TimeGenerated < windowEnd\n'
        '| where ContainerAppName_s == "wtscrm-api-prod"\n'
        '| where Log_s has "CDC: Unhandled error processing" or Log_s has "CDC: Handler error" '
        'or Log_s has "CDC: Failed to process message"\n'
        "| summarize failures = count() by Bucket = bin(TimeGenerated, 5m)\n"
        "| project Bucket, failures\n"
        "| order by Bucket asc\n"
    )


def cdc_servicebus_kql(start: int, end: int) -> str:
    return (
        _window(start, end)
        + "ContainerAppConsoleLogs_CL\n"
        "| where TimeGenerated >= windowStart and TimeGenerated < windowEnd\n"
        '| where ContainerAppName_s == "wtscrm-api-prod"\n'
        '| where Log_s has "CDC: Service Bus error"\n'
        "| summarize errors = count() by Bucket = bin(TimeGenerated, 5m)\n"
        "| project Bucket, errors\n"
        "| order by Bucket asc\n"
    )


def kql_for(kind: str, start: int, end: int) -> str:
    if kind == "requests":
        return requests_kql(start, end)
    if kind == "comvoy_ops":
        return comvoy_ops_kql(start, end)
    if kind == "cdc_handler":
        return cdc_handler_kql(start, end)
    if kind == "cdc_sb":
        return cdc_servicebus_kql(start, end)
    raise ValueError(kind)
