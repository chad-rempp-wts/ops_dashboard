# Ops dashboard

Read-only production health for the WTS Azure estate, in two forms that share one data model and one page:

| | Snapshot | Live |
|---|---|---|
| Command | `generate` | `serve` |
| Window | 7 days | 1 day |
| Bucket | 5 minutes | 1 minute |
| Output | one standalone HTML file | a page on `127.0.0.1` that follows Azure |
| Network when opened | none | polls the local server every 30 s |

There is no local database. The snapshot is the file you publish. The live view holds the current day in memory.

## Setup

```bash
cd /Users/crempp/projects/ops-dashboard
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"    # ".[live]" if you only need to run it
az login
```

Uses `DefaultAzureCredential` with the current Azure CLI login. Managed identity is excluded.

## Snapshot

```bash
python -m ops_dashboard generate --fixture --out output/           # offline, no Azure calls
python -m ops_dashboard generate --out output/                     # production
python -m ops_dashboard generate --end 2026-09-28T15:00:00Z        # fixed window end
```

Writes `output/ops-dashboard-YYYY-MM-DD.html` (Pacific date of the window end) and `output/latest.html` (same bytes).
The file inlines CSS, script, and data. It makes no requests, and a test enforces that.

## Live

```bash
python -m ops_dashboard serve                  # http://127.0.0.1:8000/
python -m ops_dashboard serve --fixture        # same page, synthetic data
python -m ops_dashboard serve --port 9000 --refresh 60
```

- The first refresh queries the whole day. Later refreshes re-query the trailing 30 minutes and roll the window forward. The whole day is re-queried hourly.
- Azure Monitor trails real time by one to three minutes, so the newest buckets fill in on later refreshes.
- The page shows a pill: **Live** (fresh), **Stale** (the last refresh failed, or nothing new for 3 minutes), or **Server unreachable**. A failed refresh keeps the last good data and says so.
- While you are hovering a chart or have it focused, a new report is held back and applied when you stop.
- Polling pauses while the tab is hidden and resumes when you return.
- It binds to `127.0.0.1` and has no login. Do not bind it to a shared interface.

Endpoints: `/` (page), `/api/report?version=N` (changed or unchanged), `/api/health` (200 once the first refresh has succeeded).

## How health is scored

The methodology at the bottom of every page is generated from `ops_dashboard/catalog.py`, so the thresholds shown are the thresholds used.

- **Failures are 5xx.** `toint(resultCode) >= 500` divided by all requests. 404 and other 4xx are not counted. "All failures" (`success == false`) is shown beside it as a fact and is not scored, because bot 404s are about 15% of dealer-site requests.
- **Rates are judged over the trailing 5 minutes** in both modes, and the 50-request volume guard uses the same window. A one-minute bucket with 3 requests cannot swing a score.
- **Shared Application Insights components are filtered by `cloud_RoleName`.** Comvoy runs under `comvoy-frontend-server` in the search API's component.
- **Linux sites do not report `HttpQueueLength`.** Comvoy and the locator use the App Service plan's queue.
- **Missing or unthresholded data is unknown, never healthy.** Headline figures use the latest sample within the last 10 minutes.
- **The CDC stall check** sums the trailing 15 minutes, anchored at the newest bucket where both counts exist.
- Comvoy alert-rule lines mirror the Azure scheduled query rules and count `success == false`, as those alerts do.

## Permissions

Read-only on the production subscription `3034dd9a-8858-4b6b-98b8-056c254828c6`:

- Reader, so resource IDs and App Service state can be confirmed
- Monitoring Reader, for Azure Monitor metrics
- Log Analytics Reader on the Application Insights components and `wtscrm-cae-prod-logs`

The non-production subscription `0aa33137-92a3-4b75-95f6-0aaccaacec7e` is out of scope. The process only sends GET and query requests.

## Tests

```bash
pytest
```

## Troubleshooting

- `DefaultAzureCredential` failed: run `az login` and `az account set --subscription 3034dd9a-8858-4b6b-98b8-056c254828c6`.
- HTTP 403 on a metric or log query: the signed-in user is missing Monitoring Reader or Log Analytics Reader on that resource. The page still renders; the component is unknown and the error is in the Data quality section.
- HTTP 429: a query is retried up to three times. A remaining failure is recorded and does not stop the report.
- A metric name is absent from a resource: optional metrics are skipped. Required metrics become unknown.
- Charts look gapped: a missing bucket is drawn as a break. Lines are not interpolated.
- Live shows **Stale**: hover the pill for the last error. The Data quality section at the bottom lists any query that failed in the latest refresh.

## Later: Blob Storage

Uploading the dated file and `latest.html` is a separate step. This project does not upload anything.
