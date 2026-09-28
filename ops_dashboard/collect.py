"""Read-only Azure queries. Failures become data-quality notes, not a crashed report."""

from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, NamedTuple, Optional, Set

import httpx
from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus

from ops_dashboard.catalog import APP_IDS, LOG_JOBS, METRIC_JOBS, LogJob, MetricJob, log_job_keys
from ops_dashboard.logs_parse import event_counts, operation_series, request_series
from ops_dashboard.metrics_parse import parse_metric_payload, supported_metric_names
from ops_dashboard.model import QueryRecord
from ops_dashboard.profile import SNAPSHOT, Profile
from ops_dashboard.queries import kql_for
from ops_dashboard.series import align_map, iter_chunks, merge_timestamp_maps
from ops_dashboard.window import iso_utc

METRIC_API = "2018-01-01"
WEB_API = "2022-03-01"
MANAGEMENT = "https://management.azure.com"
CHUNK_SECONDS = 86400


class Collected(NamedTuple):
    series: Dict[str, list]
    states: Dict[str, str]
    queries: List[QueryRecord]
    quality: List[str]
    unavailable: Set[str]


class Monitor:
    def __init__(self, credential) -> None:
        self._credential = credential
        self._client = httpx.Client(timeout=60.0)
        self._definitions: Dict[str, Optional[dict]] = {}
        self._lock = threading.Lock()

    def close(self) -> None:
        self._client.close()

    def _token(self) -> str:
        return self._credential.get_token(f"{MANAGEMENT}/.default").token

    def get(self, url: str, params: dict) -> httpx.Response:
        last_error = "request failed"
        for attempt in range(3):
            try:
                response = self._client.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {self._token()}"},
                )
            except httpx.HTTPError as exc:
                last_error = _short(exc)
                time.sleep(min(8, 2 ** attempt))
                continue
            if response.status_code in (429, 502, 503, 504):
                last_error = f"HTTP {response.status_code}"
                time.sleep(min(8, 2 ** attempt))
                continue
            return response
        raise RuntimeError(last_error)

    def definitions(self, resource_id: str) -> Optional[dict]:
        """Metric names a resource defines. Cached for the life of the process."""
        with self._lock:
            if resource_id in self._definitions:
                return self._definitions[resource_id]
        url = f"{MANAGEMENT}{resource_id}/providers/microsoft.insights/metricDefinitions"
        try:
            response = self.get(url, {"api-version": METRIC_API})
            if response.status_code >= 400:
                found = None
            else:
                found = supported_metric_names(response.json())
        except Exception:
            found = None
        with self._lock:
            self._definitions[resource_id] = found
        return found

    def query_metrics(self, resource_id: str, names: List[str], aggregation: str, start: int, end: int, dimension, dimension_value, interval: str = "PT5M") -> dict:
        params = {
            "api-version": METRIC_API,
            "metricnames": ",".join(names),
            "timespan": f"{iso_utc(start)}/{iso_utc(end)}",
            "interval": interval,
            "aggregation": aggregation,
        }
        if dimension and dimension_value:
            if "'" in dimension_value or "'" in dimension:
                raise ValueError("metric dimension values cannot contain quotes")
            params["$filter"] = f"{dimension} eq '{dimension_value}'"
        url = f"{MANAGEMENT}{resource_id}/providers/microsoft.insights/metrics"
        response = self.get(url, params)
        if response.status_code >= 400:
            detail = response.text.replace("\n", " ")[:240]
            raise RuntimeError(f"HTTP {response.status_code} {detail}")
        return response.json()

    def app_state(self, resource_id: str) -> str:
        url = f"{MANAGEMENT}{resource_id}"
        response = self.get(url, {"api-version": WEB_API})
        if response.status_code == 404:
            return "absent"
        if response.status_code in (401, 403):
            return "unknown"
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code}")
        state = str((response.json().get("properties") or {}).get("state") or "")
        if state.lower() == "stopped":
            return "stopped"
        if state:
            return "running"
        return "unknown"


class Collector:
    """Holds one credential and one HTTP client, so a live server reuses tokens and metric definitions."""

    def __init__(self, profile: Profile = SNAPSHOT, workers: int = 4, credential=None, quiet: bool = False) -> None:
        self.profile = profile
        self.workers = max(1, workers)
        self.quiet = quiet
        credential = credential or DefaultAzureCredential(exclude_managed_identity_credential=True)
        self._monitor = Monitor(credential)
        self._logs = LogsQueryClient(credential)

    def close(self) -> None:
        self._monitor.close()

    def __enter__(self) -> "Collector":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def collect(self, start: int, end: int) -> Collected:
        """Query [start, end) on the profile's grid. Series are None-filled where nothing came back."""
        step = self.profile.step
        count = (end - start) // step
        series: Dict[str, list] = {}
        states: Dict[str, str] = {}
        queries: List[QueryRecord] = []
        quality: List[str] = []
        unavailable: Set[str] = set()
        outcomes = []
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {}
            for job in METRIC_JOBS:
                futures[pool.submit(_metric_job, self._monitor, job, start, end, count, self.profile)] = ("metric", job.name)
            for job in LOG_JOBS:
                futures[pool.submit(_log_job, self._logs, job, start, end, count, self.profile)] = ("log", job.name)
            for component_id, resource_id in APP_IDS.items():
                futures[pool.submit(_state_job, self._monitor, component_id, resource_id)] = ("state", component_id)
            for future in as_completed(futures):
                kind, name = futures[future]
                try:
                    outcome = future.result()
                except Exception as exc:
                    message = _short(exc)
                    quality.append(f"{name} failed: {message}")
                    queries.append(QueryRecord(name, kind, 0, "error", message))
                    self._log(f"failed {name}: {message}")
                    continue
                outcomes.append(outcome)
                self._log(f"{outcome.status} {outcome.name} ({outcome.duration_ms} ms)")
        for outcome in outcomes:
            queries.append(outcome.record)
            if outcome.error:
                quality.append(f"{outcome.name}: {outcome.error}")
            for note in outcome.notes:
                quality.append(note)
            if outcome.kind == "state":
                states[outcome.component_id] = outcome.state
            else:
                series.update(outcome.series)
                unavailable.update(outcome.unavailable)
        return Collected(series, states, queries, quality, unavailable)

    def _log(self, message: str) -> None:
        if not self.quiet:
            print(message, file=sys.stderr)


def collect(start: int, end: int, workers: int = 4, profile: Profile = SNAPSHOT) -> Collected:
    """One-shot collection for the snapshot report."""
    with Collector(profile, workers) as collector:
        return collector.collect(start, end)


class _Outcome:
    def __init__(self, kind, name, status, duration_ms, error=None, notes=None, series=None, component_id=None, state=None, detail=""):
        self.kind = kind
        self.name = name
        self.status = status
        self.duration_ms = duration_ms
        self.error = error
        self.notes = notes or []
        self.series = series or {}
        self.unavailable = set()
        self.component_id = component_id
        self.state = state
        self.record = QueryRecord(name, kind, duration_ms, status, error, detail)


def _metric_job(monitor: Monitor, job: MetricJob, start: int, end: int, count: int, profile: Profile) -> _Outcome:
    started = time.perf_counter()
    step = profile.step
    notes: List[str] = []
    defined = monitor.definitions(job.resource_id)
    lookup = {name.lower(): name for name in (defined or {})}
    chosen = []
    unavailable = set()
    for spec in job.metrics:
        actual = lookup.get(spec.name.lower())
        if defined is not None and actual is None:
            notes.append(f"{job.name}: {spec.name} is not defined on this resource and was not queried.")
            unavailable.add(spec.key)
            continue
        chosen.append((spec, actual or spec.name))
    if not chosen:
        duration = _ms(started)
        empty = {item.key: [None] * count for item in job.metrics}
        outcome = _Outcome("metric", job.name, "error", duration, "no metrics were available", notes, empty)
        outcome.unavailable = unavailable
        return outcome
    names = [actual for _spec, actual in chosen]
    chosen_specs = {spec for spec, _actual in chosen}

    def query_names(metric_names: List[str]) -> tuple:
        found: List[dict] = []
        problems: List[str] = []
        for chunk_start, chunk_end in iter_chunks(start, end, CHUNK_SECONDS):
            try:
                payload = monitor.query_metrics(
                    job.resource_id,
                    metric_names,
                    job.aggregation,
                    chunk_start,
                    chunk_end,
                    job.dimension,
                    job.dimension_value,
                    profile.grain,
                )
                found.append(parse_metric_payload(payload, job.aggregation))
            except Exception as exc:
                problems.append(f"{iso_utc(chunk_start)}/{iso_utc(chunk_end)}: {_short(exc)}")
                if not found:
                    break
        return found, problems

    chunk_maps, errors = query_names(names)
    if errors and len(names) > 1 and not chunk_maps:
        notes.append(f"{job.name}: combined metric query failed; retrying each metric.")
        chunk_maps = []
        errors = []
        for metric_name in names:
            one_maps, one_errors = query_names([metric_name])
            chunk_maps.extend(one_maps)
            if one_errors and not one_maps:
                notes.append(f"{job.name}: {metric_name} could not be queried.")
                errors.extend(one_errors)
            elif one_errors:
                errors.extend(one_errors)
    series = {}
    actual_by_spec = {spec: actual for spec, actual in chosen}
    for spec in job.metrics:
        if spec not in chosen_specs:
            series[spec.key] = [None] * count
            continue
        actual = actual_by_spec[spec]
        merged = merge_timestamp_maps(
            [chunk.get(actual, chunk.get(spec.name, {})) for chunk in chunk_maps]
        )
        series[spec.key] = align_map(merged, start, step, count)
    status = "ok"
    error = None
    if errors and chunk_maps:
        status = "partial"
        error = "; ".join(errors)[:500]
    elif errors:
        status = "error"
        error = "; ".join(errors)[:500]
    outcome = _Outcome("metric", job.name, status, _ms(started), error, notes, series, detail=f"{job.aggregation} {profile.grain}")
    outcome.unavailable = unavailable
    return outcome


def _log_job(logs: LogsQueryClient, job: LogJob, start: int, end: int, count: int, profile: Profile) -> _Outcome:
    started = time.perf_counter()
    kql = kql_for(job.kind, start, end, profile.step, job.role)
    last_error = "log query failed"
    response = None
    for attempt in range(3):
        try:
            response = logs.query_resource(
                job.resource_id,
                kql,
                timespan=(
                    datetime.fromtimestamp(start, timezone.utc),
                    datetime.fromtimestamp(end, timezone.utc),
                ),
            )
            break
        except Exception as exc:
            last_error = _short(exc)
            if attempt == 2 or not _retryable(exc):
                empty = _empty_log(job, count)
                return _Outcome("log", job.name, "error", _ms(started), last_error, series=empty)
            time.sleep(min(8, 2 ** attempt))
    rows, partial = _rows(response)
    parsed = _parse_log(job, rows, start, count, profile.step)
    status = "partial" if partial else "ok"
    error = partial
    detail = f"role {job.role}" if job.role else ""
    return _Outcome("log", job.name, status, _ms(started), error, series=parsed, detail=detail)


def _parse_log(job: LogJob, rows: list, start: int, count: int, step: int) -> dict:
    if job.kind == "requests":
        parsed = request_series(rows, start, step, count)
        return {
            f"{job.prefix}Req": parsed["req"],
            f"{job.prefix}FailCount": parsed["failed"],
            f"{job.prefix}FailAll": parsed["failed_all"],
            f"{job.prefix}Avg": parsed["avg"],
            f"{job.prefix}P95": parsed["p95"],
        }
    if job.kind == "exceptions":
        return {f"{job.prefix}Exc": event_counts(rows, "Count", start, step, count)}
    if job.kind == "comvoy_ops":
        return operation_series(rows, start, step, count)
    if job.kind == "cdc_handler":
        return {"cdcHandler": event_counts(rows, "failures", start, step, count)}
    if job.kind == "cdc_sb":
        return {"cdcSb": event_counts(rows, "errors", start, step, count)}
    return {}


def _empty_log(job: LogJob, count: int) -> dict:
    return {key: [None] * count for key in log_job_keys(job)}


def _rows(response):
    partial = None
    if response.status == LogsQueryStatus.PARTIAL:
        tables = response.partial_data
        partial = _short(getattr(response, "partial_error", None) or "partial log result")
    else:
        tables = response.tables
    if not tables:
        return [], partial
    table = tables[0]
    names = []
    for column in table.columns:
        names.append(column.name if hasattr(column, "name") else str(column))
    rows = []
    for raw in table.rows:
        rows.append({names[index]: raw[index] for index in range(len(names))})
    return rows, partial


def _state_job(monitor: Monitor, component_id: str, resource_id: str) -> _Outcome:
    started = time.perf_counter()
    try:
        state = monitor.app_state(resource_id)
        status = "ok" if state != "unknown" else "error"
        error = None if status == "ok" else "site state could not be read"
        return _Outcome("state", f"State {component_id}", status, _ms(started), error, component_id=component_id, state=state, detail=state)
    except Exception as exc:
        return _Outcome(
            "state",
            f"State {component_id}",
            "error",
            _ms(started),
            _short(exc),
            component_id=component_id,
            state="unknown",
        )


def _retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status in (429, 502, 503, 504):
        return True
    text = str(exc).lower()
    return "429" in text or "throttl" in text or "timeout" in text or "503" in text


def _short(exc) -> str:
    return str(exc).splitlines()[0][:300]


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
