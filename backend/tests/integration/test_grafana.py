"""
Integration tests for /grafana/* endpoints.

Strategy:
  1. 401 — no token: confirms require_admin guard fires on all endpoints
  2. 503 — admin token, env vars absent: confirms "not_configured" branch in every handler
  3. 200 — admin token, env vars set, httpx mocked: exercises the full request path

All endpoints require admin JWT.  No DB rows are touched by these tests.
"""
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt

pytestmark = pytest.mark.integration


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
    assert api_client.get("/grafana/metrics", params={"query": "up"}).status_code == 401


def test_metrics_batch_no_token_returns_401(api_client):
    assert api_client.post("/grafana/metrics/batch", json=[]).status_code == 401


def test_logs_no_token_returns_401(api_client):
    assert api_client.get("/grafana/logs", params={"query": '{app="x"}'}).status_code == 401


def test_loki_metrics_batch_no_token_returns_401(api_client):
    assert api_client.post("/grafana/loki-metrics/batch", json=[]).status_code == 401


def test_logs_batch_no_token_returns_401(api_client):
    assert api_client.post("/grafana/logs/batch", json=[]).status_code == 401


def test_traces_no_token_returns_401(api_client):
    assert api_client.get("/grafana/traces").status_code == 401


def test_traces_detail_no_token_returns_401(api_client):
    assert api_client.get("/grafana/traces/abc123").status_code == 401


def test_traces_batch_no_token_returns_401(api_client):
    assert api_client.post("/grafana/traces/batch", json=[]).status_code == 401


# ---------------------------------------------------------------------------
# 503 — env vars absent → "not_configured"
# ---------------------------------------------------------------------------

_EMPTY_ENV = {
    "GRAFANA_PROMETHEUS_URL": "", "GRAFANA_PROMETHEUS_USER": "",
    "GRAFANA_LOKI_URL": "", "GRAFANA_LOKI_USER": "",
    "GRAFANA_TEMPO_URL": "", "GRAFANA_TEMPO_USER": "",
    "GRAFANA_API_KEY": "",
}


def test_metrics_not_configured_returns_503(api_client):
    with patch.dict(os.environ, _EMPTY_ENV):
        r = api_client.get("/grafana/metrics", params={"query": "up"}, headers=_HDR)
    assert r.status_code == 503
    assert r.json()["error"] == "not_configured"


def test_metrics_batch_not_configured_returns_503(api_client):
    items = [{"query": "up", "step": "60"}]
    with patch.dict(os.environ, _EMPTY_ENV):
        r = api_client.post("/grafana/metrics/batch", json=items, headers=_HDR)
    assert r.status_code == 503


def test_logs_not_configured_returns_503(api_client):
    with patch.dict(os.environ, _EMPTY_ENV):
        r = api_client.get("/grafana/logs", params={"query": '{app="x"}'}, headers=_HDR)
    assert r.status_code == 503


def test_loki_metrics_batch_not_configured_returns_503(api_client):
    items = [{"query": "up", "step": "60"}]
    with patch.dict(os.environ, _EMPTY_ENV):
        r = api_client.post("/grafana/loki-metrics/batch", json=items, headers=_HDR)
    assert r.status_code == 503


def test_logs_batch_not_configured_returns_503(api_client):
    items = [{"query": '{app="x"}', "limit": 100}]
    with patch.dict(os.environ, _EMPTY_ENV):
        r = api_client.post("/grafana/logs/batch", json=items, headers=_HDR)
    assert r.status_code == 503


def test_traces_not_configured_returns_503(api_client):
    with patch.dict(os.environ, _EMPTY_ENV):
        r = api_client.get("/grafana/traces", headers=_HDR)
    assert r.status_code == 503


def test_traces_detail_not_configured_returns_503(api_client):
    with patch.dict(os.environ, _EMPTY_ENV):
        r = api_client.get("/grafana/traces/some-trace-id", headers=_HDR)
    assert r.status_code == 503


def test_traces_batch_not_configured_returns_503(api_client):
    items = [{"q": "test"}]
    with patch.dict(os.environ, _EMPTY_ENV):
        r = api_client.post("/grafana/traces/batch", json=items, headers=_HDR)
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# 200 — env configured, httpx mocked
# ---------------------------------------------------------------------------

def test_metrics_configured_returns_200(api_client):
    mock_client = _mock_httpx_client()
    with patch.dict(os.environ, _PROM_ENV), \
         patch("backend.services.grafana_service.httpx.AsyncClient", return_value=mock_client):
        r = api_client.get("/grafana/metrics", params={"query": "up"}, headers=_HDR)
    assert r.status_code == 200


def test_metrics_batch_configured_returns_200(api_client):
    mock_client = _mock_httpx_client()
    items = [{"query": "up", "step": "60"}]
    with patch.dict(os.environ, _PROM_ENV), \
         patch("backend.routers.grafana.httpx.AsyncClient", return_value=mock_client):
        r = api_client.post("/grafana/metrics/batch", json=items, headers=_HDR)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_logs_configured_returns_200(api_client):
    mock_client = _mock_httpx_client(body={"status": "success", "data": {"result": []}})
    with patch.dict(os.environ, _LOKI_ENV), \
         patch("backend.services.grafana_service.httpx.AsyncClient", return_value=mock_client):
        r = api_client.get("/grafana/logs", params={"query": '{app="x"}'}, headers=_HDR)
    assert r.status_code == 200


def test_loki_metrics_batch_configured_returns_200(api_client):
    mock_client = _mock_httpx_client()
    items = [{"query": "up", "step": "60"}]
    with patch.dict(os.environ, _LOKI_ENV), \
         patch("backend.routers.grafana.httpx.AsyncClient", return_value=mock_client):
        r = api_client.post("/grafana/loki-metrics/batch", json=items, headers=_HDR)
    assert r.status_code == 200


def test_logs_batch_configured_returns_200(api_client):
    mock_client = _mock_httpx_client(body={"status": "success", "data": {"result": []}})
    items = [{"query": '{app="x"}', "limit": 100}]
    with patch.dict(os.environ, _LOKI_ENV), \
         patch("backend.routers.grafana.httpx.AsyncClient", return_value=mock_client):
        r = api_client.post("/grafana/logs/batch", json=items, headers=_HDR)
    assert r.status_code == 200


def test_traces_configured_returns_200(api_client):
    mock_client = _mock_httpx_client(body={"data": []})
    with patch.dict(os.environ, _TEMPO_ENV), \
         patch("backend.services.grafana_service.httpx.AsyncClient", return_value=mock_client):
        r = api_client.get("/grafana/traces", headers=_HDR)
    assert r.status_code == 200


def test_traces_detail_configured_returns_200(api_client):
    mock_client = _mock_httpx_client(body={"data": {}})
    with patch.dict(os.environ, _TEMPO_ENV), \
         patch("backend.routers.grafana.httpx.AsyncClient", return_value=mock_client):
        r = api_client.get("/grafana/traces/trace-abc", headers=_HDR)
    assert r.status_code == 200


def test_traces_batch_configured_returns_200(api_client):
    mock_client = _mock_httpx_client(body={"data": {}})
    items = [{"q": "duration>100ms"}]
    with patch.dict(os.environ, _TEMPO_ENV), \
         patch("backend.routers.grafana.httpx.AsyncClient", return_value=mock_client):
        r = api_client.post("/grafana/traces/batch", json=items, headers=_HDR)
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
