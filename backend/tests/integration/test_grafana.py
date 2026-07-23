"""
Integration tests for /grafana/* endpoints.

Strategy:
  1. 401 — no token: confirms require_admin guard fires on all endpoints
  2. 503 — admin token, env vars absent: confirms "not_configured" branch in every handler
  3. 200 — admin token, env vars set, httpx mocked: exercises the full request path

All endpoints require admin JWT.  No DB rows are touched by these tests.
"""
import importlib
import os
import time
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

pytestmark = pytest.mark.integration


@contextmanager
def _grafana_env(overrides: dict, db_session):
    """backend/routers/grafana.py does `from backend.config import GRAFANA_*`, bound once at
    import time — patch.dict(os.environ, ...) alone has no effect on it anymore. Reload
    backend.config -> backend.routers.grafana -> backend.main (in that order; each only re-binds
    to the previous module's *current* attributes on its own reload, and backend.main's `app`
    only picks up fresh route handlers by re-running its own include_router() calls), then
    re-apply the get_db override to the freshly-rebuilt app (a reload makes a new app instance,
    dropping any override set on the old one) and yield a TestClient bound to it."""
    with patch.dict(os.environ, overrides):
        import backend.config as config
        importlib.reload(config)
        import backend.routers.grafana as grafana
        importlib.reload(grafana)
        import backend.main as main
        importlib.reload(main)
        from backend.database import get_db

        def _override():
            yield db_session

        main.app.dependency_overrides[get_db] = _override
        yield TestClient(main.app)
        main.app.dependency_overrides.pop(get_db, None)
    importlib.reload(config)
    importlib.reload(grafana)
    importlib.reload(main)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _admin_token() -> str:
    return jwt.encode(
        {"sub": "admin", "role": "admin", "exp": int(time.time()) + 3600},
        "test-secret",
        algorithm="HS256",
    )


_HDR = {"Authorization": f"Bearer {_admin_token()}"}

_PROM_ENV = {
    "GRAFANA_PROMETHEUS_URL": "https://prometheus.example.com",
    "GRAFANA_PROMETHEUS_USER": "42",
    "GRAFANA_API_KEY": "glc_test_key",
}
_LOKI_ENV = {
    "GRAFANA_LOKI_URL": "https://loki.example.com",
    "GRAFANA_LOKI_USER": "42",
    "GRAFANA_API_KEY": "glc_test_key",
}
_TEMPO_ENV = {
    "GRAFANA_TEMPO_URL": "https://tempo.example.com",
    "GRAFANA_TEMPO_USER": "42",
    "GRAFANA_API_KEY": "glc_test_key",
}


def _mock_httpx_client(status: int = 200, body=None):
    """Return an AsyncMock that mimics httpx.AsyncClient as an async context manager."""
    if body is None:
        body = {"status": "success", "data": {"resultType": "matrix", "result": []}}
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=resp)
    client.post = AsyncMock(return_value=resp)
    return client


# ---------------------------------------------------------------------------
# 401 — no token
# ---------------------------------------------------------------------------

def test_metrics_no_token_returns_401(api_client):
    assert api_client.app_client.get("/grafana/metrics", params={"query": "up"}).status_code == 401


def test_metrics_batch_no_token_returns_401(api_client):
    assert api_client.app_client.post("/grafana/metrics/batch", json=[]).status_code == 401


def test_logs_no_token_returns_401(api_client):
    assert api_client.app_client.get("/grafana/logs", params={"query": '{app="x"}'}).status_code == 401


def test_loki_metrics_batch_no_token_returns_401(api_client):
    assert api_client.app_client.post("/grafana/loki-metrics/batch", json=[]).status_code == 401


def test_logs_batch_no_token_returns_401(api_client):
    assert api_client.app_client.post("/grafana/logs/batch", json=[]).status_code == 401


def test_traces_no_token_returns_401(api_client):
    assert api_client.app_client.get("/grafana/traces").status_code == 401


def test_traces_detail_no_token_returns_401(api_client):
    assert api_client.app_client.get("/grafana/traces/abc123").status_code == 401


def test_traces_batch_no_token_returns_401(api_client):
    assert api_client.app_client.post("/grafana/traces/batch", json=[]).status_code == 401


# ---------------------------------------------------------------------------
# 503 — env vars absent → "not_configured"
# ---------------------------------------------------------------------------

_EMPTY_ENV = {
    "GRAFANA_PROMETHEUS_URL": "", "GRAFANA_PROMETHEUS_USER": "",
    "GRAFANA_LOKI_URL": "", "GRAFANA_LOKI_USER": "",
    "GRAFANA_TEMPO_URL": "", "GRAFANA_TEMPO_USER": "",
    "GRAFANA_API_KEY": "",
}


def test_metrics_not_configured_returns_503(db_session):
    with _grafana_env(_EMPTY_ENV, db_session) as client:
        r = client.get("/grafana/metrics", params={"query": "up"}, headers=_HDR)
    assert r.status_code == 503
    assert r.json()["error"] == "not_configured"


def test_metrics_batch_not_configured_returns_503(db_session):
    items = [{"query": "up", "step": "60"}]
    with _grafana_env(_EMPTY_ENV, db_session) as client:
        r = client.post("/grafana/metrics/batch", json=items, headers=_HDR)
    assert r.status_code == 503


def test_logs_not_configured_returns_503(db_session):
    with _grafana_env(_EMPTY_ENV, db_session) as client:
        r = client.get("/grafana/logs", params={"query": '{app="x"}'}, headers=_HDR)
    assert r.status_code == 503


def test_loki_metrics_batch_not_configured_returns_503(db_session):
    items = [{"query": "up", "step": "60"}]
    with _grafana_env(_EMPTY_ENV, db_session) as client:
        r = client.post("/grafana/loki-metrics/batch", json=items, headers=_HDR)
    assert r.status_code == 503


def test_logs_batch_not_configured_returns_503(db_session):
    items = [{"query": '{app="x"}', "limit": 100}]
    with _grafana_env(_EMPTY_ENV, db_session) as client:
        r = client.post("/grafana/logs/batch", json=items, headers=_HDR)
    assert r.status_code == 503


def test_traces_not_configured_returns_503(db_session):
    with _grafana_env(_EMPTY_ENV, db_session) as client:
        r = client.get("/grafana/traces", headers=_HDR)
    assert r.status_code == 503


def test_traces_detail_not_configured_returns_503(db_session):
    with _grafana_env(_EMPTY_ENV, db_session) as client:
        r = client.get("/grafana/traces/some-trace-id", headers=_HDR)
    assert r.status_code == 503


def test_traces_batch_not_configured_returns_503(db_session):
    items = [{"q": "test"}]
    with _grafana_env(_EMPTY_ENV, db_session) as client:
        r = client.post("/grafana/traces/batch", json=items, headers=_HDR)
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# 200 — env configured, httpx mocked
# ---------------------------------------------------------------------------

def test_metrics_configured_returns_200(db_session):
    mock_client = _mock_httpx_client()
    with _grafana_env(_PROM_ENV, db_session) as client, \
         patch("backend.services.grafana_service.httpx.AsyncClient", return_value=mock_client):
        r = client.get("/grafana/metrics", params={"query": "up"}, headers=_HDR)
    assert r.status_code == 200


def test_metrics_batch_configured_returns_200(db_session):
    mock_client = _mock_httpx_client()
    items = [{"query": "up", "step": "60"}]
    with _grafana_env(_PROM_ENV, db_session) as client, \
         patch("backend.routers.grafana.httpx.AsyncClient", return_value=mock_client):
        r = client.post("/grafana/metrics/batch", json=items, headers=_HDR)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_logs_configured_returns_200(db_session):
    mock_client = _mock_httpx_client(body={"status": "success", "data": {"result": []}})
    with _grafana_env(_LOKI_ENV, db_session) as client, \
         patch("backend.services.grafana_service.httpx.AsyncClient", return_value=mock_client):
        r = client.get("/grafana/logs", params={"query": '{app="x"}'}, headers=_HDR)
    assert r.status_code == 200


def test_loki_metrics_batch_configured_returns_200(db_session):
    mock_client = _mock_httpx_client()
    items = [{"query": "up", "step": "60"}]
    with _grafana_env(_LOKI_ENV, db_session) as client, \
         patch("backend.routers.grafana.httpx.AsyncClient", return_value=mock_client):
        r = client.post("/grafana/loki-metrics/batch", json=items, headers=_HDR)
    assert r.status_code == 200


def test_logs_batch_configured_returns_200(db_session):
    mock_client = _mock_httpx_client(body={"status": "success", "data": {"result": []}})
    items = [{"query": '{app="x"}', "limit": 100}]
    with _grafana_env(_LOKI_ENV, db_session) as client, \
         patch("backend.routers.grafana.httpx.AsyncClient", return_value=mock_client):
        r = client.post("/grafana/logs/batch", json=items, headers=_HDR)
    assert r.status_code == 200


def test_traces_configured_returns_200(db_session):
    mock_client = _mock_httpx_client(body={"data": []})
    with _grafana_env(_TEMPO_ENV, db_session) as client, \
         patch("backend.services.grafana_service.httpx.AsyncClient", return_value=mock_client):
        r = client.get("/grafana/traces", headers=_HDR)
    assert r.status_code == 200


def test_traces_detail_configured_returns_200(db_session):
    mock_client = _mock_httpx_client(body={"data": {}})
    with _grafana_env(_TEMPO_ENV, db_session) as client, \
         patch("backend.routers.grafana.httpx.AsyncClient", return_value=mock_client):
        r = client.get("/grafana/traces/trace-abc", headers=_HDR)
    assert r.status_code == 200


def test_traces_batch_configured_returns_200(db_session):
    mock_client = _mock_httpx_client(body={"data": {}})
    items = [{"q": "duration>100ms"}]
    with _grafana_env(_TEMPO_ENV, db_session) as client, \
         patch("backend.routers.grafana.httpx.AsyncClient", return_value=mock_client):
        r = client.post("/grafana/traces/batch", json=items, headers=_HDR)
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# grafana_service.py — auth_headers helper
# ---------------------------------------------------------------------------

def test_auth_headers_returns_basic_auth():
    from backend.services.grafana_service import auth_headers

    headers = auth_headers("user123", "my-api-key")
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Basic ")


def test_auth_headers_empty_creds_returns_empty():
    from backend.services.grafana_service import auth_headers

    assert auth_headers("", "") == {}
    assert auth_headers("user", "") == {}
    assert auth_headers("", "key") == {}
