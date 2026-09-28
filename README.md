"""How to generate the daily systems report.

The report is one HTML file. Each run queries Azure Monitor, Application Insights,
and Log Analytics directly, builds an in-memory model, and writes the file.
There is no local database and no upload step.

## Setup

```bash
cd /Users/crempp/projects/daily-system-report
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
az login
```

The generator uses `DefaultAzureCredential` and the current Azure CLI login.
It does not read secrets from Terraform or from CI2 Datadog keys.

## Run

Offline fixture (no Azure calls):

```bash
python -m report generate --fixture --out output/
```

Live read-only production report. The window ends at the latest completed
five-minute boundary unless you pass `--end`:

```bash
python -m report generate --out output/
python -m report generate --end 2026-09-28T15:00:00Z --out output/
```

Outputs:

- `output/daily-report-YYYY-MM-DD.html` (Pacific date of the window end)
- `output/latest.html` (same bytes)

Open either file from disk. It does not request a network, a CDN, or a server.

## Permissions

Read-only on the production subscription `3034dd9a-8858-4b6b-98b8-056c254828c6`
(WTS via BizSpark, converted to EA):

- Reader, so resource IDs and App Service state can be confirmed
- Monitoring Reader, for Azure Monitor metrics
- Log Analytics Reader on Application Insights components and `wtscrm-cae-prod-logs`

Non-production subscription `0aa33137-92a3-4b75-95f6-0aaccaacec7e` is out of scope.

The process only sends GET and query requests. It does not create or change Azure resources.

## Tests

```bash
pytest
```

## Troubleshooting

- `DefaultAzureCredential` failed: run `az login` and `az account set --subscription 3034dd9a-8858-4b6b-98b8-056c254828c6`.
- HTTP 403 on a metric or log query: the signed-in user is missing Monitoring Reader or Log Analytics Reader on that resource. The report still renders; the affected component is unknown and the error is in the data-quality section.
- HTTP 429: the generator retries a query up to three times. A remaining failure is recorded and does not stop the file from being written.
- A metric name is absent from a resource: optional metrics are skipped. Required metrics become unknown.
- Charts look gapped: a missing five-minute bucket is drawn as a break. The line is not interpolated.

## Later: Blob Storage

Uploading the dated file and `latest.html` is a separate step. This project does not upload anything and does not create a storage account.
