from report.metrics_parse import parse_metric_payload


def test_average_is_not_replaced_by_total():
    payload = {
        "value": [
            {
                "name": {"value": "Percentage5XX"},
                "timeseries": [
                    {
                        "data": [
                            {
                                "timeStamp": "2026-09-28T00:00:00Z",
                                "total": 100,
                                "average": 0.2,
                            },
                            {
                                "timeStamp": "2026-09-28T00:05:00Z",
                                "total": 50,
                                "average": None,
                            },
                        ]
                    }
                ],
            }
        ]
    }
    parsed = parse_metric_payload(payload, "Average")
    points = list(parsed["Percentage5XX"].values())
    assert points == [0.2, None]


def test_total_aggregation_reads_total_only():
    payload = {
        "value": [
            {
                "name": {"value": "RequestCount"},
                "timeseries": [
                    {"data": [{"timeStamp": "2026-09-28T00:00:00Z", "total": 12, "average": 99}]}
                ],
            }
        ]
    }
    parsed = parse_metric_payload(payload, "Total")
    assert list(parsed["RequestCount"].values()) == [12.0]
