import re

from fastapi.testclient import TestClient

from ops_dashboard.live import FixtureEngine
from ops_dashboard.serve import create_app


def _client(primed=True):
    engine = FixtureEngine(clock=lambda: 1_790_000_040.0)
    if primed:
        engine.refresh()
    return TestClient(create_app(engine, refresh_seconds=3600)), engine


def test_index_serves_the_live_page():
    with _client()[0] as client:
        response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert 'data-mode="live"' in html
    assert 'id="live-pill"' in html
    assert "fetch(" in html
    assert "'/api/report" in html
    assert response.headers["cache-control"] == "no-store"
    assert re.search(r'data-version="\d+"', html)


def test_api_report_reports_unchanged_and_changed():
    with _client()[0] as client:
        first = client.get("/api/report").json()
        assert first["changed"] is True
        assert first["payload"]["mode"] == "live"
        assert first["payload"]["count"] == 1440
        assert 'id="app"' not in first["body"]
        same = client.get("/api/report", params={"version": first["version"]}).json()
        assert same["changed"] is False
        assert "body" not in same
        assert same["status"]["ok"] is True


def test_health_reflects_readiness():
    client, engine = _client(primed=False)
    engine.refresh = lambda: None  # keep the background loop from priming it
    with client:
        assert client.get("/api/health").status_code == 503
        assert client.get("/api/report").status_code == 503
        assert client.get("/").status_code == 503
        FixtureEngine.refresh(engine)
        assert client.get("/api/health").status_code == 200


def test_openapi_and_docs_are_not_exposed():
    with _client()[0] as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
