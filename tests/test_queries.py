from report.catalog import LOG_JOBS, METRIC_JOBS, DEALER_AI
from report.queries import cdc_handler_kql, requests_kql


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
