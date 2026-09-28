"""Production component manifest. Resource IDs were read from Azure, not guessed.

Non-production subscription 0aa33137-92a3-4b75-95f6-0aaccaacec7e is out of scope.
The autoscale setting name contains 80; its rule body is not encoded.
CDC topic depth is not queried: an unused default subscription dominates it.

Request reliability is scored on server errors (5xx) only. Application Insights also marks
404 and other 4xx responses as failed, and bot traffic makes those about 15% of dealer-site
requests, so `success == false` is kept as an unscored fact ("all failures").

Several services share one Application Insights component. Every request and exception
query for them is filtered by cloud_RoleName (`LogJob.role`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

SUBSCRIPTION_ID = "3034dd9a-8858-4b6b-98b8-056c254828c6"
SCHEMA_VERSION = 1
MIN_REQUESTS = 50.0
CPU_WARN = 70.0
CPU_CRIT = 85.0
QUEUE_WARN = 1.0
QUEUE_CRIT = 10.0
FAIL_WARN = 1.0
FAIL_CRIT = 3.0
DEALER_DURATION_CRIT = 2000.0
SEARCH_THROTTLE_CRIT = 0.1
EMAIL_DLQ_BASELINE = 4.0
CDC_STALL_MINUTES = 15
RATE_WINDOW_MINUTES = 5

# Comvoy scheduled-query rules read 2026-09-28 from resource group wts-prod.
# Severity 0 is critical. Severity 2 is degraded. Operators are GreaterThan.
COMVOY_SRP_FAIL_PCT = 20.0
COMVOY_SRP_MIN_REQUESTS = 200.0
COMVOY_SRP_MINUTES = 30
COMVOY_SRP_VOLUME = 100000.0
COMVOY_SRP_VOLUME_MINUTES = 10
COMVOY_LEAD_FAIL_PCT = 50.0
COMVOY_LEAD_MIN_REQUESTS = 3.0
COMVOY_LEAD_MINUTES = 30

AUTOSCALE_SETTING = "wts-prod-dealersite-appsvcplan-Autoscale-80"


def arm(group: str, path: str) -> str:
    return f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{group}/providers/{path}"


FD1 = arm("FrontDoor", "Microsoft.Cdn/profiles/wts-frontdoor-prod-1")
FD2 = arm("FrontDoor", "Microsoft.Cdn/profiles/wts-frontdoor-prod-2")
SQL = arm("Default-SQL-NorthCentralUS", "Microsoft.Sql/servers/k2682gqujp/databases/WTS")
DEALER_SITE = arm("wts-prod", "Microsoft.Web/sites/wts-prod-dealersite")
DEALER_PLAN = arm("wts-prod", "Microsoft.Web/serverFarms/wts-prod-dealersite-appsvcplan")
DEALER_AI = arm("wts-prod-40", "microsoft.insights/components/Production-DealerSite")
WEBAPI_SITE = arm("wts-prod", "Microsoft.Web/sites/wts-prod-webapi")
WEBAPI_PLAN = arm("wts-prod", "Microsoft.Web/serverFarms/wts-prod-app-svc-plan")
WEBAPI_AI = arm("wts-prod-rg", "microsoft.insights/components/wtsWebApi-AppInsights")
SEARCH_SITE = arm("wts-prod", "Microsoft.Web/sites/wts-prod-searchwebapi")
SEARCH_AI = arm("wts-prod", "microsoft.insights/components/wts-prod-searchwebapi")
# Comvoy telemetry lands in the search API's component under its own role name.
# The component named comvoy-frontend-prod-linux exists and receives nothing.
COMVOY_AI = SEARCH_AI

ROLE_DEALER = "wts-prod-dealersite"
ROLE_WEBAPI = "wts-prod-webapi"
ROLE_SEARCH = "wts-search-webapi"
ROLE_COMVOY = "comvoy-frontend-server"
TOOLS_SITE = arm("wts-prod", "Microsoft.Web/sites/wts-prod-dealertoolswebapi")
TOOLS_AI = arm("wts-prod", "microsoft.insights/components/wts-prod-dealertoolswebapi")
COMVOY_SITE = arm("wts-prod", "Microsoft.Web/sites/comvoy-frontend-prod-linux")
COMVOY_PLAN = arm("wts-prod", "Microsoft.Web/serverFarms/comvoy-frontend-prod-linux")
LOCATOR_SITE = arm("wts-prod", "Microsoft.Web/sites/wts-prod-locator-frontend")
LOCATOR_AI = arm("wts-prod", "microsoft.insights/components/wts-prod-locator-frontend")
WEBJOBS_SITE = arm("wts-prod", "Microsoft.Web/sites/wts-prod-webjobs")
WEBJOBS_AI = arm("wts-prod", "microsoft.insights/components/wts-prod-webjobs")
SIGNALR = arm("wts-prod", "Microsoft.SignalRService/SignalR/wts-prod-signalr")
SEARCH_SERVICE = arm("wts-prod", "Microsoft.Search/searchServices/wts-prod-search-service")
PUBLIC_API = arm("wts-prod", "Microsoft.Web/sites/wts-prod-publicapi")
GATEWAY = arm("wts-crm-prod", "Microsoft.Network/applicationGateways/wtscrm-gateway-prod")
CRM_API = arm("wts-crm-prod", "Microsoft.App/containerApps/wtscrm-api-prod")
TRACKER_SITE = arm("wts-crm-prod", "Microsoft.Web/sites/wts-crm-prod-datachangetracker")
TRACKER_PLAN = arm("wts-crm-prod", "Microsoft.Web/serverFarms/NorthCentralUSPlan")
TRACKER_AI = arm("wts-crm-prod", "Microsoft.Insights/components/wts-crm-prod-datachangetracker")
EMAIL_SITE = arm("wts-crm-prod", "Microsoft.Web/sites/wtscrm-emailpipeline-production")
EMAIL_PLAN = arm("wts-crm-prod", "Microsoft.Web/serverFarms/wtscrm-emailpipeline-plan-production")
EMAIL_AI = arm("wts-crm-prod", "Microsoft.Insights/components/wtscrm-empipe-ai-production")
CRM_BUS = arm("wts-crm-prod", "Microsoft.ServiceBus/namespaces/wts-crm-prod-servicebus")
EMAIL_BUS = arm("wts-crm-prod", "Microsoft.ServiceBus/namespaces/wtscrm-empipe-sb-production")
REDIS = arm("wts-crm-prod", "Microsoft.Cache/redisEnterprise/wtscrm-redis-prod")
CRM_LOGS = arm("wts-crm-prod", "Microsoft.OperationalInsights/workspaces/wtscrm-cae-prod-logs")

SHARE_DEALER_PLAN = (
    "Shares wts-prod-dealersite-appsvcplan with the dealer site, search API, and dealer-tools API"
)
SHARE_APP_PLAN = "Shares wts-prod-app-svc-plan with Web API and WebJobs"
SHARE_COMVOY_PLAN = "Shares comvoy-frontend-prod-linux with Comvoy and the locator"


@dataclass(frozen=True)
class MetricSpec:
    key: str
    name: str
    required: bool = True


@dataclass(frozen=True)
class MetricJob:
    name: str
    resource_id: str
    aggregation: str
    metrics: Tuple[MetricSpec, ...]
    dimension: Optional[str] = None
    dimension_value: Optional[str] = None


@dataclass(frozen=True)
class LogJob:
    name: str
    resource_id: str
    kind: str
    prefix: str
    # cloud_RoleName filter for components that several services report into.
    role: Optional[str] = None


@dataclass(frozen=True)
class ThresholdRule:
    series: str
    noun: str
    fmt: str
    warning: Optional[float] = None
    critical: Optional[float] = None
    op: str = "gte"
    volume_series: Optional[str] = None
    min_volume: Optional[float] = None


@dataclass(frozen=True)
class Display:
    series: Optional[str]
    fmt: str
    unit: str
    reduce: str
    literal: Optional[str] = None


@dataclass(frozen=True)
class ChartSpec:
    id: str
    caption: str
    fmt: str
    series: Tuple[Tuple[str, str], ...]
    note: str
    scale: str = "auto"
    volume: Optional[str] = None
    sum_series: bool = False
    # When set, the axis stops at this quantile of the data so rare spikes do not flatten the line.
    cap_quantile: Optional[float] = None


@dataclass(frozen=True)
class Component:
    id: str
    title: str
    layer: str
    row: int
    stack: str
    icon: str
    runtime: str
    resource: str
    share: Optional[str] = None
    mode: str = "rules"  # rules | unthresholded | absent
    reliability: str = "score"  # score | sparse
    request_series: Optional[str] = None
    rules: Tuple[ThresholdRule, ...] = ()
    displays: Tuple[Display, ...] = ()
    facts: Tuple[Display, ...] = ()
    charts: Tuple[ChartSpec, ...] = ()
    app_id: Optional[str] = None
    presence_id: Optional[str] = None
    fixture_maintenance: bool = False


def _cpu(series: str, noun: str) -> ThresholdRule:
    return ThresholdRule(series, noun, "pct1", CPU_WARN, CPU_CRIT, "gte")


def _mem(series: str, noun: str) -> ThresholdRule:
    return ThresholdRule(series, noun, "pct1", CPU_WARN, CPU_CRIT, "gte")


def _queue(series: str, noun: str) -> ThresholdRule:
    return ThresholdRule(series, noun, "int", QUEUE_WARN, QUEUE_CRIT, "gte")


def _fail(series: str, volume: str, noun: str) -> ThresholdRule:
    return ThresholdRule(
        series, noun, "pct2", FAIL_WARN, FAIL_CRIT, "gte", volume, MIN_REQUESTS
    )


def _plan_metrics(prefix: str) -> Tuple[MetricSpec, ...]:
    return (
        MetricSpec(f"{prefix}Cpu", "CpuPercentage"),
        MetricSpec(f"{prefix}Mem", "MemoryPercentage"),
    )


METRIC_JOBS: Tuple[MetricJob, ...] = (
    MetricJob("Front Door prod-1 requests", FD1, "Total", (MetricSpec("fd1Req", "RequestCount"),)),
    MetricJob(
        "Front Door prod-1 latency and 5xx",
        FD1,
        "Average",
        (MetricSpec("fd1Lat", "OriginLatency"), MetricSpec("fd1P5", "Percentage5XX")),
    ),
    MetricJob("Front Door prod-2 requests", FD2, "Total", (MetricSpec("fd2Req", "RequestCount"),)),
    MetricJob(
        "Front Door prod-2 latency and 5xx",
        FD2,
        "Average",
        (MetricSpec("fd2Lat", "OriginLatency"), MetricSpec("fd2P5", "Percentage5XX")),
    ),
    MetricJob(
        "Azure SQL",
        SQL,
        "Average",
        (
            MetricSpec("sqlCpu", "cpu_percent"),
            MetricSpec("sqlWorkers", "workers_percent", False),
            MetricSpec("sqlStorage", "storage_percent", False),
            MetricSpec("sqlConnFail", "connection_failed", False),
            MetricSpec("sqlDtu", "dtu_consumption_percent", False),
        ),
    ),
    MetricJob("Dealer App Service plan", DEALER_PLAN, "Average", _plan_metrics("plan")),
    MetricJob("Web API App Service plan", WEBAPI_PLAN, "Average", _plan_metrics("appPlan")),
    # Linux App Service does not expose RequestsInApplicationQueue on the site.
    # The plan's HttpQueueLength is the queue signal for Comvoy and the locator.
    MetricJob(
        "Comvoy App Service plan",
        COMVOY_PLAN,
        "Average",
        (*_plan_metrics("comvoyPlan"), MetricSpec("comvoyPlanQueue", "HttpQueueLength", False)),
    ),
    MetricJob("Tracker App Service plan", TRACKER_PLAN, "Average", _plan_metrics("trackerPlan")),
    MetricJob("Email App Service plan", EMAIL_PLAN, "Average", _plan_metrics("emailPlan")),
    MetricJob("Dealer site platform", DEALER_SITE, "Total", (MetricSpec("dealerHttp5xx", "Http5xx"),)),
    MetricJob(
        "Dealer site platform averages",
        DEALER_SITE,
        "Average",
        (MetricSpec("dealerHttpRt", "HttpResponseTime"), MetricSpec("dealerQueue", "RequestsInApplicationQueue")),
    ),
    MetricJob("Web API platform", WEBAPI_SITE, "Total", (MetricSpec("webapiHttp5xx", "Http5xx"),)),
    MetricJob(
        "Web API platform averages",
        WEBAPI_SITE,
        "Average",
        (MetricSpec("webapiHttpRt", "HttpResponseTime"), MetricSpec("webapiQueue", "RequestsInApplicationQueue")),
    ),
    MetricJob("Search API platform", SEARCH_SITE, "Total", (MetricSpec("searchapiHttp5xx", "Http5xx"),)),
    MetricJob(
        "Search API platform averages",
        SEARCH_SITE,
        "Average",
        (MetricSpec("searchapiHttpRt", "HttpResponseTime"), MetricSpec("searchapiQueue", "RequestsInApplicationQueue")),
    ),
    MetricJob("Dealer-tools platform", TOOLS_SITE, "Total", (MetricSpec("toolsHttp5xx", "Http5xx"),)),
    MetricJob(
        "Dealer-tools platform averages",
        TOOLS_SITE,
        "Average",
        (MetricSpec("toolsHttpRt", "HttpResponseTime"), MetricSpec("toolsQueue", "RequestsInApplicationQueue")),
    ),
    MetricJob("Comvoy platform", COMVOY_SITE, "Total", (MetricSpec("comvoyHttp5xx", "Http5xx"),)),
    MetricJob(
        "Comvoy platform averages",
        COMVOY_SITE,
        "Average",
        (MetricSpec("comvoyHttpRt", "HttpResponseTime"),),
    ),
    MetricJob("Locator platform", LOCATOR_SITE, "Total", (MetricSpec("locatorHttp5xx", "Http5xx"),)),
    MetricJob(
        "Locator platform averages",
        LOCATOR_SITE,
        "Average",
        (MetricSpec("locatorHttpRt", "HttpResponseTime"),),
    ),
    MetricJob("WebJobs platform", WEBJOBS_SITE, "Total", (MetricSpec("webjobsHttp5xx", "Http5xx"),)),
    MetricJob(
        "WebJobs platform averages",
        WEBJOBS_SITE,
        "Average",
        (MetricSpec("webjobsHttpRt", "HttpResponseTime"), MetricSpec("webjobsQueue", "RequestsInApplicationQueue")),
    ),
    MetricJob("Tracker platform", TRACKER_SITE, "Total", (MetricSpec("trackerHttp5xx", "Http5xx"),)),
    MetricJob(
        "Tracker platform averages",
        TRACKER_SITE,
        "Average",
        (MetricSpec("trackerHttpRt", "HttpResponseTime"), MetricSpec("trackerQueue", "RequestsInApplicationQueue")),
    ),
    MetricJob("Email platform", EMAIL_SITE, "Total", (MetricSpec("emailHttp5xx", "Http5xx"),)),
    MetricJob(
        "Email platform averages",
        EMAIL_SITE,
        "Average",
        (MetricSpec("emailHttpRt", "HttpResponseTime"), MetricSpec("emailQueue", "RequestsInApplicationQueue")),
    ),
    MetricJob(
        "Azure AI Search",
        SEARCH_SERVICE,
        "Average",
        (
            MetricSpec("searchThrottle", "ThrottledSearchQueriesPercentage"),
            MetricSpec("searchLatency", "SearchLatency"),
        ),
    ),
    MetricJob(
        "SignalR",
        SIGNALR,
        "Average",
        (
            MetricSpec("signalrConn", "ConnectionCount", False),
            MetricSpec("signalrLoad", "ServerLoad", False),
        ),
    ),
    MetricJob(
        "CRM Redis",
        REDIS,
        "Average",
        (
            MetricSpec("redisMem", "usedmemorypercentage", False),
            MetricSpec("redisClients", "connectedclients", False),
            MetricSpec("redisHits", "cachehits", False),
            MetricSpec("redisLoad", "serverLoad", False),
        ),
    ),
    MetricJob(
        "CRM gateway totals",
        GATEWAY,
        "Total",
        (
            MetricSpec("gwFail", "FailedRequests"),
            MetricSpec("gwTotal", "TotalRequests"),
        ),
    ),
    MetricJob(
        "CRM gateway hosts",
        GATEWAY,
        "Average",
        (MetricSpec("gwUnhealthy", "UnhealthyHostCount", False),),
    ),
    MetricJob(
        "CRM API restarts",
        CRM_API,
        "Maximum",
        (MetricSpec("crmRestarts", "RestartCount"),),
    ),
    MetricJob(
        "CRM API usage",
        CRM_API,
        "Average",
        (
            MetricSpec("crmCpu", "CpuPercentage", False),
            MetricSpec("crmMem", "MemoryPercentage", False),
            MetricSpec("crmCores", "UsageNanoCores", False),
            MetricSpec("crmWorkingSet", "WorkingSetBytes", False),
        ),
    ),
    MetricJob(
        "CDC data-changes flow",
        CRM_BUS,
        "Total",
        (
            MetricSpec("cdcIn", "IncomingMessages"),
            MetricSpec("cdcOut", "OutgoingMessages"),
        ),
        "EntityName",
        "data-changes",
    ),
    MetricJob(
        "Notifications dead letters",
        CRM_BUS,
        "Average",
        (MetricSpec("notifyDlq", "DeadletteredMessages"),),
        "EntityName",
        "notifications",
    ),
    MetricJob(
        "Email scan dead letters",
        EMAIL_BUS,
        "Average",
        (MetricSpec("emailDlq", "DeadletteredMessages"),),
        "EntityName",
        "email-scan-jobs",
    ),
)

LOG_JOBS: Tuple[LogJob, ...] = (
    LogJob("Dealer site requests", DEALER_AI, "requests", "dealer", ROLE_DEALER),
    LogJob("Web API requests", WEBAPI_AI, "requests", "webapi", ROLE_WEBAPI),
    LogJob("Search API requests", SEARCH_AI, "requests", "searchapi", ROLE_SEARCH),
    LogJob("Dealer-tools requests", TOOLS_AI, "requests", "tools"),
    LogJob("Comvoy requests", COMVOY_AI, "requests", "comvoy", ROLE_COMVOY),
    LogJob("Dealer site exceptions", DEALER_AI, "exceptions", "dealer", ROLE_DEALER),
    LogJob("Web API exceptions", WEBAPI_AI, "exceptions", "webapi", ROLE_WEBAPI),
    LogJob("Search API exceptions", SEARCH_AI, "exceptions", "searchapi", ROLE_SEARCH),
    LogJob("Comvoy exceptions", COMVOY_AI, "exceptions", "comvoy", ROLE_COMVOY),
    LogJob("Locator requests", LOCATOR_AI, "requests", "locator"),
    LogJob("WebJobs requests", WEBJOBS_AI, "requests", "webjobs"),
    LogJob("Tracker requests", TRACKER_AI, "requests", "tracker"),
    LogJob("Email pipeline requests", EMAIL_AI, "requests", "email"),
    LogJob("Comvoy search operations", SEARCH_AI, "comvoy_ops", "comvoyOps"),
    LogJob("CDC handler failures", CRM_LOGS, "cdc_handler", "cdcHandler"),
    LogJob("CDC Service Bus errors", CRM_LOGS, "cdc_sb", "cdcSb"),
)

APP_IDS = {
    "dealer": DEALER_SITE,
    "webapi": WEBAPI_SITE,
    "searchapi": SEARCH_SITE,
    "tools": TOOLS_SITE,
    "comvoy": COMVOY_SITE,
    "locator": LOCATOR_SITE,
    "webjobs": WEBJOBS_SITE,
    "tracker": TRACKER_SITE,
    "email": EMAIL_SITE,
    "publicapi": PUBLIC_API,
}

EDGES = (
    ("fd", "dealer", 0),
    ("fd", "comvoy", 0),
    ("fd", "locator", 0),
    ("gateway", "crmapi", 0),
    ("dealer", "webapi", 0),
    ("dealer", "tools", 0),
    ("comvoy", "searchapi", 0),
    ("locator", "searchapi", 0),
    ("webapi", "signalr", 0),
    ("webapi", "sql", 0),
    ("searchapi", "search", 0),
    ("searchapi", "sql", 0),
    ("tools", "sql", 0),
    ("webjobs", "sql", 0),
    ("crmapi", "tracker", 0),
    ("crmapi", "email", 0),
    ("crmapi", "redis", 0),
    ("crmapi", "sql", 0),
    ("tracker", "sb", 0),
    ("email", "sb", 0),
    ("dealer", "plan", 1),
    ("searchapi", "plan", 1),
    ("tools", "plan", 1),
)

LAYERS = (
    (2, "Edge"),
    (3, "Presentation"),
    (4, "APIs"),
    (5, "Workers"),
    (6, "Messaging"),
    (7, "Data and platform"),
)

_FAIL_NOTE = (
    "5xx responses divided by all requests, over the trailing 5 minutes. 404 and other 4xx are not counted. "
    "Scored only when those 5 minutes have at least 50 requests. Gaps are missing samples, not zero."
)


def _fail_chart(prefix: str, title: str) -> ChartSpec:
    return ChartSpec(
        f"{prefix}Rate",
        f"{title} server-error (5xx) percent",
        "pct2",
        ((f"{prefix}Rate", "Server errors (5xx)"),),
        _FAIL_NOTE,
        volume=f"{prefix}Req",
    )


COMPONENTS: Tuple[Component, ...] = (
    Component(
        "fd", "Front Door", "Edge", 2, "wts", "frontdoor", "Azure Front Door",
        "wts-frontdoor-prod-1 and wts-frontdoor-prod-2",
        mode="unthresholded",
        displays=(
            Display("fd1Req", "int", "prod-1 requests / 5 min", "last"),
            Display("fd2Req", "int", "prod-2 requests / 5 min", "last"),
            Display("fd1P5", "pct2", "prod-1 5xx", "last"),
        ),
        facts=(
            Display("fd1Lat", "ms", "prod-1 origin latency", "last"),
            Display("fd2Lat", "ms", "prod-2 origin latency", "last"),
            Display("fd2P5", "pct2", "prod-2 5xx", "last"),
            Display("fd1Req", "int", "prod-1 peak requests", "peak"),
        ),
        charts=(
            ChartSpec(
                "fdReq",
                "Front Door requests per 5 minutes, both profiles",
                "int",
                (("fd1Req", "wts-frontdoor-prod-1"), ("fd2Req", "wts-frontdoor-prod-2")),
                "RequestCount uses Total. Origin latency and Percentage5XX use Average and are not summed. No warning threshold is configured.",
                sum_series=True,
            ),
        ),
    ),
    Component(
        "dealer", "Dealer site", "Presentation", 3, "wts", "appservice", "ASP.NET",
        "wts-prod-dealersite",
        share=SHARE_DEALER_PLAN,
        reliability="score",
        request_series="dealerReq",
        app_id=DEALER_SITE,
        rules=(
            _fail("dealerRate", "dealerReq", "Server errors (5xx)"),
            _queue("dealerQueue", "HTTP queue"),
            ThresholdRule("dealerAvg", "Average request duration", "ms", None, DEALER_DURATION_CRIT, "gt"),
        ),
        displays=(
            Display("dealerRate", "pct2", "server errors (5xx)", "last"),
            Display("dealerReq", "int", "requests / 5 min", "last"),
            Display("dealerAvg", "ms", "average duration", "last"),
        ),
        facts=(
            Display("dealerP95", "ms", "p95 duration", "last"),
            Display("dealerQueue", "int", "HTTP queue", "last"),
            Display("dealerHttp5xx", "int", "platform Http5xx", "last"),
            Display("planCpu", "pct1", "shared plan CPU", "last"),
            Display("dealerRateAll", "pct2", "all failures incl. 404, not scored", "last"),
            Display("dealerExc", "int", "exceptions / 5 min", "last"),
        ),
        charts=(
            _fail_chart("dealer", "Dealer site"),
            ChartSpec(
                "dealerAvg",
                "Dealer site average request duration",
                "ms",
                (("dealerAvg", "Average duration"), ("dealerP95", "p95 duration")),
                "Critical line is the average-duration alert at 2,000 ms. p95 is shown and is not the scored line. Gaps match missing request buckets.",
                cap_quantile=0.98,
            ),
        ),
    ),
    Component(
        "comvoy", "Comvoy frontend", "Presentation", 3, "wts", "svelte", "SvelteKit",
        "comvoy-frontend-prod-linux",
        share=SHARE_COMVOY_PLAN,
        reliability="score",
        request_series="comvoyReq",
        app_id=COMVOY_SITE,
        rules=(
            _fail("comvoyRate", "comvoyReq", "Server errors (5xx)"),
            _cpu("comvoyPlanCpu", "Comvoy plan CPU"),
            _mem("comvoyPlanMem", "Comvoy plan memory"),
            _queue("comvoyPlanQueue", "Plan HTTP queue"),
        ),
        displays=(
            Display("comvoyRate", "pct2", "server errors (5xx)", "last"),
            Display("comvoyReq", "int", "requests / 5 min", "last"),
            Display("comvoyPlanCpu", "pct1", "plan CPU", "last"),
        ),
        facts=(
            Display("comvoyHttp5xx", "int", "platform Http5xx", "last"),
            Display("comvoyPlanMem", "pct1", "plan memory", "last"),
            Display("comvoyPlanQueue", "int", "plan HTTP queue", "last"),
            Display("comvoyHttpRt", "ms", "platform response", "last"),
            Display("comvoyRateAll", "pct2", "all failures incl. 404, not scored", "last"),
            Display("comvoyExc", "int", "exceptions / 5 min", "last"),
        ),
        charts=(
            _fail_chart("comvoy", "Comvoy frontend"),
            ChartSpec(
                "comvoy5xx",
                "Comvoy platform Http5xx count",
                "int",
                (("comvoyHttp5xx", "Http5xx"),),
                "App Service platform metric, counted by the platform rather than by Application Insights. It has no separate threshold.",
            ),
        ),
    ),
    Component(
        "locator", "Locator frontend", "Presentation", 3, "wts", "locator", "Linux App Service",
        "wts-prod-locator-frontend",
        share=SHARE_COMVOY_PLAN,
        reliability="score",
        request_series="locatorReq",
        app_id=LOCATOR_SITE,
        rules=(_fail("locatorRate", "locatorReq", "Server errors (5xx)"), _queue("comvoyPlanQueue", "Plan HTTP queue")),
        displays=(
            Display("locatorRate", "pct2", "server errors (5xx)", "last"),
            Display("locatorReq", "int", "requests / 5 min", "last"),
            Display("comvoyPlanCpu", "pct1", "shared plan CPU", "last"),
        ),
        facts=(
            Display("locatorHttp5xx", "int", "platform Http5xx", "last"),
            Display("comvoyPlanQueue", "int", "shared plan HTTP queue", "last"),
            Display("locatorRateAll", "pct2", "all failures incl. 404, not scored", "last"),
        ),
        charts=(_fail_chart("locator", "Locator"),),
    ),
    Component(
        "webapi", "Web API", "APIs", 4, "wts", "appservice", ".NET",
        "wts-prod-webapi",
        share=SHARE_APP_PLAN,
        request_series="webapiReq",
        app_id=WEBAPI_SITE,
        rules=(
            _fail("webapiRate", "webapiReq", "Server errors (5xx)"),
            _queue("webapiQueue", "HTTP queue"),
            _cpu("appPlanCpu", "Shared plan CPU"),
            _mem("appPlanMem", "Shared plan memory"),
        ),
        displays=(
            Display("webapiRate", "pct2", "server errors (5xx)", "last"),
            Display("webapiReq", "int", "requests / 5 min", "last"),
            Display("appPlanCpu", "pct1", "plan CPU", "last"),
        ),
        facts=(
            Display("webapiP95", "ms", "p95 duration", "last"),
            Display("webapiQueue", "int", "HTTP queue", "last"),
            Display("webapiHttp5xx", "int", "platform Http5xx", "last"),
            Display("appPlanMem", "pct1", "plan memory", "last"),
            Display("webapiRateAll", "pct2", "all failures incl. 404, not scored", "last"),
            Display("webapiExc", "int", "exceptions / 5 min", "last"),
        ),
        charts=(_fail_chart("webapi", "Web API"),),
    ),
    Component(
        "searchapi", "Search API", "APIs", 4, "wts", "appservice", ".NET",
        "wts-prod-searchwebapi",
        share=SHARE_DEALER_PLAN,
        request_series="searchapiReq",
        app_id=SEARCH_SITE,
        rules=(
            _fail("searchapiRate", "searchapiReq", "Server errors (5xx)"),
            _queue("searchapiQueue", "HTTP queue"),
        ),
        displays=(
            Display("searchapiRate", "pct2", "server errors (5xx)", "last"),
            Display("searchapiReq", "int", "requests / 5 min", "last"),
            Display("planCpu", "pct1", "shared plan CPU", "last"),
        ),
        facts=(
            Display("searchapiP95", "ms", "p95 duration", "last"),
            Display("searchapiQueue", "int", "HTTP queue", "last"),
            Display("searchapiHttp5xx", "int", "platform Http5xx", "last"),
            Display("searchapiRateAll", "pct2", "all failures incl. 404, not scored", "last"),
            Display("searchapiExc", "int", "exceptions / 5 min", "last"),
        ),
        charts=(_fail_chart("searchapi", "Search API"),),
    ),
    Component(
        "tools", "Dealer-tools API", "APIs", 4, "wts", "appservice", ".NET",
        "wts-prod-dealertoolswebapi",
        share=SHARE_DEALER_PLAN,
        request_series="toolsReq",
        app_id=TOOLS_SITE,
        rules=(_fail("toolsRate", "toolsReq", "Server errors (5xx)"), _queue("toolsQueue", "HTTP queue")),
        displays=(
            Display("toolsRate", "pct2", "server errors (5xx)", "last"),
            Display("toolsReq", "int", "requests / 5 min", "last"),
            Display("planCpu", "pct1", "shared plan CPU", "last"),
        ),
        facts=(
            Display("toolsP95", "ms", "p95 duration", "last"),
            Display("toolsQueue", "int", "HTTP queue", "last"),
            Display("toolsHttp5xx", "int", "platform Http5xx", "last"),
            Display("toolsRateAll", "pct2", "all failures incl. 404, not scored", "last"),
        ),
        charts=(_fail_chart("tools", "Dealer-tools API"),),
    ),
    Component(
        "crmapi", "CRM API", "APIs", 4, "crm", "container", "Container App",
        "wtscrm-api-prod",
        rules=(
            ThresholdRule("crmRestarts", "Restarts", "int", None, 0.0, "gt"),
            ThresholdRule("cdcHandler", "CDC handler failures", "int", None, 0.0, "gt"),
            ThresholdRule("cdcSb", "CDC Service Bus errors", "int", None, 0.0, "gt"),
        ),
        displays=(
            Display("crmRestarts", "int", "restarts / 5 min", "last"),
            Display("cdcHandler", "int", "CDC handler failures", "last"),
            Display("crmCpu", "pct1", "CPU", "last"),
        ),
        facts=(
            Display("cdcSb", "int", "Service Bus receive errors", "last"),
            Display("crmMem", "pct1", "memory", "last"),
            Display("crmWorkingSet", "int", "working set bytes", "last"),
        ),
        charts=(
            ChartSpec(
                "crmRestarts",
                "CRM container restarts per 5 minutes",
                "int",
                (("crmRestarts", "Restarts"),),
                "Any restart in a 5-minute bucket is critical. RestartCount uses Maximum.",
            ),
        ),
    ),
    Component(
        "webjobs", "WebJobs host", "Workers", 5, "wts", "webjobs", ".NET",
        "wts-prod-webjobs",
        share=SHARE_APP_PLAN,
        reliability="sparse",
        request_series="webjobsReq",
        app_id=WEBJOBS_SITE,
        rules=(_queue("webjobsQueue", "HTTP queue"),),
        displays=(
            Display("webjobsReq", "int", "requests with telemetry", "completeness"),
            Display("appPlanCpu", "pct1", "shared plan CPU", "last"),
            Display("webjobsQueue", "int", "HTTP queue", "last"),
        ),
        facts=(
            Display("webjobsHttp5xx", "int", "platform Http5xx", "last"),
            Display("appPlanMem", "pct1", "shared plan memory", "last"),
        ),
        charts=(
            ChartSpec(
                "webjobsReq",
                "WebJobs request count, where a sample exists",
                "int",
                (("webjobsReq", "Requests"),),
                "Request reliability is not scored at 5-minute resolution. Empty space is missing telemetry, not zero. Plan CPU is scored on Web API, which shares wts-prod-app-svc-plan.",
            ),
        ),
    ),
    Component(
        "tracker", "CRM data-change tracker", "Workers", 5, "crm", "tracker", "App Service",
        "wts-crm-prod-datachangetracker",
        request_series="trackerReq",
        app_id=TRACKER_SITE,
        fixture_maintenance=True,
        rules=(
            _cpu("trackerPlanCpu", "Tracker plan CPU"),
            _mem("trackerPlanMem", "Tracker plan memory"),
            _fail("trackerRate", "trackerReq", "Server errors (5xx)"),
        ),
        displays=(
            Display("trackerRate", "pct2", "server errors (5xx)", "last"),
            Display("trackerReq", "int", "requests / 5 min", "last"),
            Display("trackerPlanCpu", "pct1", "plan CPU", "last"),
        ),
        facts=(
            Display("trackerQueue", "int", "HTTP queue", "last"),
            Display("trackerPlanMem", "pct1", "plan memory", "last"),
        ),
        charts=(_fail_chart("tracker", "CRM data-change tracker"),),
    ),
    Component(
        "email", "CRM email pipeline", "Workers", 5, "crm", "email", "App Service",
        "wtscrm-emailpipeline-production",
        app_id=EMAIL_SITE,
        rules=(
            ThresholdRule("emailDlq", "Email scan dead letters", "int", EMAIL_DLQ_BASELINE, None, "gt"),
            _cpu("emailPlanCpu", "Email plan CPU"),
            _queue("emailQueue", "HTTP queue"),
        ),
        displays=(
            Display("emailDlq", "int", "dead letters", "last"),
            Display("emailReq", "int", "requests / 5 min", "last"),
            Display("emailPlanCpu", "pct1", "plan CPU", "last"),
        ),
        facts=(
            Display("emailQueue", "int", "HTTP queue", "last"),
            Display("emailHttp5xx", "int", "platform Http5xx", "last"),
        ),
        charts=(
            ChartSpec(
                "emailDlq",
                "Email scan dead letters",
                "int",
                (("emailDlq", "Dead letters"),),
                "Degraded above the baseline of 4 on email-scan-jobs. The baseline was last set to 4 in alerts.parameters.production.json.",
            ),
        ),
    ),
    Component(
        "signalr", "SignalR", "Messaging", 6, "wts", "signalr", "Azure SignalR",
        "wts-prod-signalr",
        mode="unthresholded",
        displays=(
            Display("signalrConn", "int", "connections", "last"),
            Display("signalrLoad", "pct1", "server load", "last"),
            Display("signalrConn", "int", "peak connections", "peak"),
        ),
        facts=(Display("signalrLoad", "pct1", "server load", "last"),),
        charts=(
            ChartSpec(
                "signalrConn",
                "SignalR connections",
                "int",
                (("signalrConn", "Connections"),),
                "No connection cap is configured. The series is shown and is not scored.",
            ),
        ),
    ),
    Component(
        "sb", "CRM Service Bus", "Messaging", 6, "crm", "servicebus", "Azure Service Bus",
        "wts-crm-prod-servicebus",
        rules=(
            ThresholdRule("notifyDlq", "Notification dead letters", "int", 0.0, None, "gt"),
        ),
        displays=(
            Display("notifyDlq", "int", "notification dead letters", "last"),
            Display("cdcIn", "int", "data-changes incoming / 5 min", "last"),
            Display("cdcOut", "int", "data-changes outgoing / 5 min", "last"),
        ),
        facts=(
            Display("cdcIn", "int", "incoming, latest bucket", "last"),
            Display("cdcOut", "int", "outgoing, latest bucket", "last"),
        ),
        charts=(
            ChartSpec(
                "notifyDlq",
                "Notification dead letters",
                "int",
                (("notifyDlq", "Dead letters"),),
                "Degraded above 0 on the notifications topic (alert severity 2). data-changes topic depth is not charted.",
            ),
        ),
    ),
    Component(
        "sql", "Azure SQL", "Data and platform", 7, "wts", "sql", "Azure SQL",
        "WTS on k2682gqujp",
        rules=(_cpu("sqlCpu", "CPU"),),
        displays=(
            Display("sqlCpu", "pct1", "CPU", "last"),
            Display("sqlCpu", "pct1", "peak CPU", "peak"),
            Display("sqlWorkers", "pct1", "workers", "last"),
        ),
        facts=(
            Display("sqlStorage", "pct1", "storage", "last"),
            Display("sqlConnFail", "int", "connection failures", "last"),
            Display("sqlDtu", "pct1", "DTU", "last"),
        ),
        charts=(
            ChartSpec(
                "sqlCpu",
                "Azure SQL CPU percent",
                "pct1",
                (("sqlCpu", "CPU"),),
                "cpu_percent uses Average. Warning is 70% and critical is 85%. Other SQL metrics are shown only when the database defines them.",
                scale="percent100",
            ),
        ),
    ),
    Component(
        "search", "Azure AI Search", "Data and platform", 7, "wts", "search", "Azure AI Search",
        "wts-prod-search-service",
        rules=(ThresholdRule("searchThrottle", "Throttled queries", "pct3", None, SEARCH_THROTTLE_CRIT, "gt"),),
        displays=(
            Display("searchThrottle", "pct3", "throttled queries", "last"),
            Display("searchLatency", "ms", "search latency", "last"),
            Display("searchThrottle", "pct3", "peak throttled", "peak"),
        ),
        facts=(Display("searchLatency", "ms", "search latency", "last"),),
        charts=(
            ChartSpec(
                "searchThrottle",
                "Azure AI Search throttled-query percent",
                "pct3",
                (("searchThrottle", "Throttled queries"),),
                "Critical above 0.1%. The scale includes that line. Search latency is shown and is not scored.",
            ),
        ),
    ),
    Component(
        "redis", "CRM Redis Enterprise", "Data and platform", 7, "crm", "redis", "Azure Cache",
        "wtscrm-redis-prod",
        mode="unthresholded",
        displays=(
            Display("redisMem", "pct1", "used memory", "last"),
            Display("redisClients", "int", "connected clients", "last"),
            Display("redisHits", "int", "cache hits / 5 min", "last"),
        ),
        facts=(
            Display("redisLoad", "pct1", "server load", "last"),
            Display("redisMem", "pct1", "peak memory", "peak"),
        ),
        charts=(
            ChartSpec(
                "redisMem",
                "CRM Redis used memory",
                "pct1",
                (("redisMem", "Used memory"),),
                "No memory threshold is configured. 100% is the top of the scale when the metric is a percent.",
                scale="percent100",
            ),
        ),
    ),
    Component(
        "plan", "App Service plan", "Data and platform", 7, "wts", "plan", "App Service plan",
        "wts-prod-dealersite-appsvcplan",
        share="Shared by the dealer site, the search API, and the dealer-tools API",
        rules=(_cpu("planCpu", "CPU"), _mem("planMem", "Memory")),
        displays=(
            Display("planCpu", "pct1", "CPU", "last"),
            Display("planMem", "pct1", "memory", "last"),
            Display("planCpu", "pct1", "peak CPU", "peak"),
        ),
        facts=(Display("planMem", "pct1", "memory", "last"),),
        charts=(
            ChartSpec(
                "planCpu",
                "App Service plan CPU and memory",
                "pct1",
                (("planCpu", "Plan CPU"), ("planMem", "Plan memory")),
                "Shared by the dealer site, the search API, and the dealer-tools API. Warning is 70% and critical is 85% for both series. The autoscale setting name contains 80; that number is not a threshold.",
                scale="percent100",
            ),
        ),
    ),
    Component(
        "gateway", "CRM Application Gateway", "Edge", 2, "crm", "gateway", "Application Gateway",
        "wtscrm-gateway-prod",
        mode="unthresholded",
        displays=(
            Display("gwTotal", "int", "requests / 5 min", "last"),
            Display("gwRate", "pct2", "failed requests", "last"),
            Display("gwUnhealthy", "int", "unhealthy hosts", "last"),
        ),
        facts=(
            Display("gwFail", "int", "failed requests", "last"),
            Display("gwTotal", "int", "requests", "last"),
        ),
        charts=(
            ChartSpec(
                "gwRate",
                "CRM Application Gateway failed-request percent",
                "pct2",
                (("gwRate", "Failed requests"),),
                "Computed from FailedRequests and TotalRequests. No gateway failure threshold is configured, so this is not scored. Gaps are buckets with no requests or no sample.",
                volume="gwTotal",
            ),
        ),
    ),
    Component(
        "publicapi", "Public API", "APIs", 4, "wts", "appservice", "App Service",
        "wts-prod-publicapi",
        mode="absent",
        presence_id=PUBLIC_API,
        displays=(Display(None, "text", "", "literal", "Absent"),),
    ),
)

RATE_PAIRS = (
    ("dealerRate", "dealerReq", "dealerFailCount"),
    ("webapiRate", "webapiReq", "webapiFailCount"),
    ("searchapiRate", "searchapiReq", "searchapiFailCount"),
    ("toolsRate", "toolsReq", "toolsFailCount"),
    ("comvoyRate", "comvoyReq", "comvoyFailCount"),
    ("locatorRate", "locatorReq", "locatorFailCount"),
    ("webjobsRate", "webjobsReq", "webjobsFailCount"),
    ("trackerRate", "trackerReq", "trackerFailCount"),
    ("emailRate", "emailReq", "emailFailCount"),
    ("gwRate", "gwTotal", "gwFail"),
    # Unscored context: everything Application Insights marks as failed, including 404.
    ("dealerRateAll", "dealerReq", "dealerFailAll"),
    ("webapiRateAll", "webapiReq", "webapiFailAll"),
    ("searchapiRateAll", "searchapiReq", "searchapiFailAll"),
    ("toolsRateAll", "toolsReq", "toolsFailAll"),
    ("comvoyRateAll", "comvoyReq", "comvoyFailAll"),
    ("locatorRateAll", "locatorReq", "locatorFailAll"),
)


def metric_keys() -> Tuple[str, ...]:
    keys = []
    for job in METRIC_JOBS:
        for spec in job.metrics:
            keys.append(spec.key)
    return tuple(keys)


def log_job_keys(job: LogJob) -> Tuple[str, ...]:
    """Series keys a log job produces. Also the shape of an empty result."""
    if job.kind == "requests":
        return (
            f"{job.prefix}Req",
            f"{job.prefix}FailCount",
            f"{job.prefix}FailAll",
            f"{job.prefix}Avg",
            f"{job.prefix}P95",
        )
    if job.kind == "exceptions":
        return (f"{job.prefix}Exc",)
    if job.kind == "comvoy_ops":
        return ("srpReq", "srpFail", "leadReq", "leadFail")
    if job.kind == "cdc_handler":
        return ("cdcHandler",)
    if job.kind == "cdc_sb":
        return ("cdcSb",)
    return ()


def log_series_keys() -> Tuple[str, ...]:
    keys = []
    for job in LOG_JOBS:
        keys.extend(log_job_keys(job))
    return tuple(keys)


def all_series_keys() -> Tuple[str, ...]:
    derived = tuple(item[0] for item in RATE_PAIRS)
    return tuple(dict.fromkeys((*metric_keys(), *log_series_keys(), *derived)))
