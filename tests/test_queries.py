from ops_dashboard.catalog import COMVOY_AI, DEALER_AI, LOG_JOBS, METRIC_JOBS, ROLE_COMVOY, SEARCH_AI
from ops_dashboard.queries import cdc_handler_kql, exceptions_kql, kql_for, requests_kql


def test_requests_query_uses_sampled_counts_and_a_time_grid():
    query = requests_kql(0, 3000)
    assert "sum(itemCount)" in query
    assert "AppRequests" not in query
    assert "requests" in query
    assert "step 5m" in query
    assert "join kind=leftouter" in query


def test_cdc_query_matches_the_three_error_strings():
    query = cdc_handler_kql(0, 3000)
    assert "CDC: Unhandled error processing" in query
    assert "CDC: Handler error" in query
    assert "CDC: Failed to process message" in query
    assert "ContainerAppConsoleLogs_CL" in query
    assert 'ContainerAppName_s == "wtscrm-api-prod"' in query


def test_dealer_requests_use_the_production_dealersite_component():
    job = next(item for item in LOG_JOBS if item.name == "Dealer site requests")
    assert job.resource_id == DEALER_AI
    assert "Production-DealerSite" in job.resource_id
    assert "wts-prod-40" in job.resource_id


def test_cdc_topic_depth_is_not_queried():
    for job in METRIC_JOBS:
        names = [spec.name for spec in job.metrics]
        if job.dimension_value == "data-changes":
            assert "ActiveMessages" not in names
            assert "DeadletteredMessages" not in names
            assert "IncomingMessages" in names
            assert "OutgoingMessages" in names


def test_failures_are_5xx_and_all_failures_are_kept_separately():
    query = requests_kql(0, 3000)
    assert "toint(resultCode) >= 500" in query
    assert "FailedAll = sumif(itemCount, success == false)" in query


def test_one_minute_grid_uses_the_step():
    assert "step 1m" in requests_kql(0, 3000, step=60)
    assert "bin(timestamp, 1m)" in exceptions_kql(0, 3000, step=60)
    assert "step 5m" in kql_for("requests", 0, 3000)


def test_role_scoping_filters_and_rejects_unsafe_names():
    query = requests_kql(0, 3000, role=ROLE_COMVOY)
    assert f'| where cloud_RoleName == "{ROLE_COMVOY}"' in query
    assert "cloud_RoleName" not in requests_kql(0, 3000)
    try:
        requests_kql(0, 3000, role='x" or 1==1 //')
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe role name accepted")


def test_comvoy_reads_the_search_api_component_by_role():
    assert COMVOY_AI == SEARCH_AI
    job = next(item for item in LOG_JOBS if item.name == "Comvoy requests")
    assert job.resource_id == SEARCH_AI
    assert job.role == ROLE_COMVOY


def test_linux_sites_use_the_plan_queue_metric():
    names = [spec.name for job in METRIC_JOBS for spec in job.metrics]
    assert "HttpQueueLength" in names
    keys = [spec.key for job in METRIC_JOBS for spec in job.metrics]
    assert "comvoyPlanQueue" in keys
