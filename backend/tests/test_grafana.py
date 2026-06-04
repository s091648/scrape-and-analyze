import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from jose import jwt

os.environ["NEXTAUTH_SECRET"] = "test-secret"
SECRET = "test-secret"

_PROMETHEUS_ENV = {
    "GRAFANA_PROMETHEUS_URL": "https://prometheus.example.com/api/prom",
    "GRAFANA_PROMETHEUS_USER": "12345",
    "GRAFANA_API_KEY": "glc_test",
}
_LOKI_ENV = {
    "GRAFANA_LOKI_URL": "https://loki.example.com",
    "GRAFANA_LOKI_USER": "12345",
    "GRAFANA_API_KEY": "glc_test",
}
_TEMPO_ENV = {
    "GRAFANA_TEMPO_URL": "https://tempo.example.com",
    "GRAFANA_TEMPO_USER": "12345",
    "GRAFANA_API_KEY": "glc_test",
}
_UNCONFIGURED = {"GRAFANA_PROMETHEUS_URL": "", "GRAFANA_PROMETHEUS_USER": "", "GRAFANA_LOKI_URL": "", "GRAFANA_LOKI_USER": "", "GRAFANA_TEMPO_URL": "", "GRAFANA_TEMPO_USER": "", "GRAFANA_API_KEY": ""}


def admin_token():
    return jwt.encode(
        {"sub": "admin", "role": "admin", "exp": int(time.time()) + 3600},
        SECRET, algorithm="HS256",
    )


def auth():
    return {"Authorization": f"Bearer {admin_token()}"}


def _mock_httpx(status: int = 200, body: dict | list | None = None):
    """Return a mock httpx.AsyncClient usable as an async context manager."""
    if body is None:
        body = {"status": "success", "data": {"resultType": "matrix", "result": []}}
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get = AsyncMock(return_value=resp)
    return client


# ── Auth checks ────────────────────────────────────────────────────────────────

def test_metrics_no_auth_returns_401():
    from backend.main import app
    assert TestClient(app).get("/grafana/metrics", params={"query": "up"}).status_code == 401


def test_traces_no_auth_returns_401():
    from backend.main import app
    assert TestClient(app).get("/grafana/traces").status_code == 401


def test_metrics_batch_no_auth_returns_401():
    from backend.main import app
    assert TestClient(app).post("/grafana/metrics/batch", json=[]).status_code == 401


def test_logs_no_auth_returns_401():
    from backend.main import app
    assert TestClient(app).get("/grafana/logs", params={"query": '{app="x"}'}).status_code == 401


def test_traces_batch_no_auth_returns_401():
    from backend.main import app
    assert TestClient(app).post("/grafana/traces/batch", json=[]).status_code == 401


# ── Not-configured (503) ────────────────────────────────────────────────────────

def test_metrics_not_configured_returns_503():
    from backend.main import app
    with patch.dict(os.environ, _UNCONFIGURED):
        resp = TestClient(app).get("/grafana/metrics", params={"query": "up"}, headers=auth())
    assert resp.status_code == 503
    assert resp.json()["error"] == "not_configured"


def test_metrics_batch_not_configured_returns_503():
    from backend.main import app
    with patch.dict(os.environ, _UNCONFIGURED):
        resp = TestClient(app).post("/grafana/metrics/batch", json=[{"query": "up"}], headers=auth())
    assert resp.status_code == 503


def test_logs_not_configured_returns_503():
    from backend.main import app
    with patch.dict(os.environ, _UNCONFIGURED):
        resp = TestClient(app).get("/grafana/logs", params={"query": '{app="x"}'}, headers=auth())
    assert resp.status_code == 503
    assert resp.json()["error"] == "not_configured"


def test_logs_batch_not_configured_returns_503():
    from backend.main import app
    with patch.dict(os.environ, _UNCONFIGURED):
        resp = TestClient(app).post("/grafana/logs/batch", json=[{"query": '{app="x"}'}], headers=auth())
    assert resp.status_code == 503


def test_loki_metrics_batch_not_configured_returns_503():
    from backend.main import app
    with patch.dict(os.environ, _UNCONFIGURED):
        resp = TestClient(app).post("/grafana/loki-metrics/batch", json=[{"query": 'count_over_time({app="x"}[1h])'}], headers=auth())
    assert resp.status_code == 503


def test_traces_not_configured_returns_503():
    from backend.main import app
    with patch.dict(os.environ, _UNCONFIGURED):
        resp = TestClient(app).get("/grafana/traces", headers=auth())
    assert resp.status_code == 503
    assert resp.json()["error"] == "not_configured"


def test_trace_by_id_not_configured_returns_503():
    from backend.main import app
    with patch.dict(os.environ, _UNCONFIGURED):
        resp = TestClient(app).get("/grafana/traces/abc123", headers=auth())
    assert resp.status_code == 503


def test_traces_batch_not_configured_returns_503():
    from backend.main import app
    with patch.dict(os.environ, _UNCONFIGURED):
        resp = TestClient(app).post("/grafana/traces/batch", json=[{}], headers=auth())
    assert resp.status_code == 503


# ── Happy path ─────────────────────────────────────────────────────────────────

def test_metrics_returns_prometheus_body():
    from backend.main import app
    body = {"status": "success", "data": {"resultType": "matrix", "result": []}}
    with patch.dict(os.environ, _PROMETHEUS_ENV):
        with patch("httpx.AsyncClient", return_value=_mock_httpx(200, body)):
            resp = TestClient(app).get("/grafana/metrics", params={"query": "up"}, headers=auth())
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


def test_metrics_batch_returns_list_of_same_length():
    from backend.main import app
    items = [{"query": "up"}, {"query": "scrape_duration_seconds"}]
    body = {"status": "success", "data": {"resultType": "matrix", "result": []}}
    with patch.dict(os.environ, _PROMETHEUS_ENV):
        with patch("httpx.AsyncClient", return_value=_mock_httpx(200, body)):
            resp = TestClient(app).post("/grafana/metrics/batch", json=items, headers=auth())
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_logs_returns_loki_body():
    from backend.main import app
    body = {"status": "success", "data": {"resultType": "streams", "result": []}}
    with patch.dict(os.environ, _LOKI_ENV):
        with patch("httpx.AsyncClient", return_value=_mock_httpx(200, body)):
            resp = TestClient(app).get("/grafana/logs", params={"query": '{app="x"}'}, headers=auth())
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


def test_logs_batch_returns_list_of_same_length():
    from backend.main import app
    items = [{"query": '{app="x"}'}, {"query": '{app="y"}'}]
    body = {"status": "success", "data": {"resultType": "streams", "result": []}}
    with patch.dict(os.environ, _LOKI_ENV):
        with patch("httpx.AsyncClient", return_value=_mock_httpx(200, body)):
            resp = TestClient(app).post("/grafana/logs/batch", json=items, headers=auth())
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_loki_metrics_batch_returns_list_of_same_length():
    from backend.main import app
    items = [{"query": 'count_over_time({app="x"}[1h])'}]
    body = {"status": "success", "data": {"resultType": "matrix", "result": []}}
    with patch.dict(os.environ, _LOKI_ENV):
        with patch("httpx.AsyncClient", return_value=_mock_httpx(200, body)):
            resp = TestClient(app).post("/grafana/loki-metrics/batch", json=items, headers=auth())
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_traces_returns_tempo_body():
    from backend.main import app
    body = {"traces": [{"traceID": "abc", "rootServiceName": "backend"}]}
    with patch.dict(os.environ, _TEMPO_ENV):
        with patch("httpx.AsyncClient", return_value=_mock_httpx(200, body)):
            resp = TestClient(app).get("/grafana/traces", params={"q": '{service.name="backend"}'}, headers=auth())
    assert resp.status_code == 200
    assert "traces" in resp.json()


def test_trace_by_id_normalises_resource_spans_to_batches():
    """Tempo OTLP JSON uses resourceSpans; backend normalises it to batches."""
    from backend.main import app
    otlp_body = {"resourceSpans": [{"resource": {}, "scopeSpans": []}]}
    resp_mock = MagicMock()
    resp_mock.status_code = 200
    resp_mock.json.return_value = otlp_body
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get = AsyncMock(return_value=resp_mock)
    with patch.dict(os.environ, _TEMPO_ENV):
        with patch("httpx.AsyncClient", return_value=mock_client):
            resp = TestClient(app).get("/grafana/traces/trace-abc-123", headers=auth())
    assert resp.status_code == 200
    data = resp.json()
    assert "batches" in data
    assert "resourceSpans" not in data


def test_trace_by_id_preserves_existing_batches_field():
    from backend.main import app
    body = {"batches": [{"resource": {}, "instrumentationLibrarySpans": []}]}
    with patch.dict(os.environ, _TEMPO_ENV):
        with patch("httpx.AsyncClient", return_value=_mock_httpx(200, body)):
            resp = TestClient(app).get("/grafana/traces/trace-xyz", headers=auth())
    assert resp.status_code == 200
    assert "batches" in resp.json()


def test_traces_batch_returns_list_of_same_length():
    from backend.main import app
    items = [{"q": '{service.name="backend"}', "limit": 5}, {"limit": 10}]
    body = {"traces": []}
    with patch.dict(os.environ, _TEMPO_ENV):
        with patch("httpx.AsyncClient", return_value=_mock_httpx(200, body)):
            resp = TestClient(app).post("/grafana/traces/batch", json=items, headers=auth())
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ── Edge cases: invalid JSON responses ────────────────────────────────────────

def _mock_httpx_invalid_json(status: int = 200):
    """Return a mock client whose .json() raises ValueError (non-JSON body)."""
    resp = MagicMock()
    resp.status_code = status
    resp.json.side_effect = ValueError("not json")
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get = AsyncMock(return_value=resp)
    return client


def test_grafana_get_returns_invalid_response_on_non_json_body():
    """_grafana_get wraps non-JSON response bodies as {'error': 'invalid_response'}."""
    from backend.main import app
    with patch.dict(os.environ, _PROMETHEUS_ENV):
        with patch("httpx.AsyncClient", return_value=_mock_httpx_invalid_json(200)):
            resp = TestClient(app).get("/grafana/metrics", params={"query": "up"}, headers=auth())
    assert resp.json()["error"] == "invalid_response"


def test_get_trace_by_id_returns_invalid_response_on_non_json_body():
    """get_trace_by_id wraps non-JSON Tempo responses as {'error': 'invalid_response'}."""
    from backend.main import app
    with patch.dict(os.environ, _TEMPO_ENV):
        with patch("httpx.AsyncClient", return_value=_mock_httpx_invalid_json(200)):
            resp = TestClient(app).get("/grafana/traces/abc123", headers=auth())
    assert resp.json()["error"] == "invalid_response"


# ── Edge cases: fetch_one exception in batch endpoints ────────────────────────

def _mock_httpx_raises():
    """Return a mock client whose .get() raises a network error."""
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get = AsyncMock(side_effect=Exception("connection refused"))
    return client


def test_metrics_batch_returns_invalid_response_on_fetch_exception():
    from backend.main import app
    with patch.dict(os.environ, _PROMETHEUS_ENV):
        with patch("httpx.AsyncClient", return_value=_mock_httpx_raises()):
            resp = TestClient(app).post(
                "/grafana/metrics/batch",
                json=[{"query": "up"}],
                headers=auth(),
            )
    assert resp.status_code == 200
    assert resp.json()[0]["error"] == "invalid_response"


def test_logs_batch_returns_invalid_response_on_fetch_exception():
    from backend.main import app
    with patch.dict(os.environ, _LOKI_ENV):
        with patch("httpx.AsyncClient", return_value=_mock_httpx_raises()):
            resp = TestClient(app).post(
                "/grafana/logs/batch",
                json=[{"query": '{app="x"}'}],
                headers=auth(),
            )
    assert resp.status_code == 200
    assert resp.json()[0]["error"] == "invalid_response"


def test_loki_metrics_batch_returns_invalid_response_on_fetch_exception():
    from backend.main import app
    with patch.dict(os.environ, _LOKI_ENV):
        with patch("httpx.AsyncClient", return_value=_mock_httpx_raises()):
            resp = TestClient(app).post(
                "/grafana/loki-metrics/batch",
                json=[{"query": 'count_over_time({app="x"}[1h])'}],
                headers=auth(),
            )
    assert resp.status_code == 200
    assert resp.json()[0]["error"] == "invalid_response"


def test_traces_batch_returns_invalid_response_on_fetch_exception():
    from backend.main import app
    with patch.dict(os.environ, _TEMPO_ENV):
        with patch("httpx.AsyncClient", return_value=_mock_httpx_raises()):
            resp = TestClient(app).post(
                "/grafana/traces/batch",
                json=[{"limit": 5}],
                headers=auth(),
            )
    assert resp.status_code == 200
    assert resp.json()[0]["error"] == "invalid_response"


# ── Optional query parameters ─────────────────────────────────────────────────

def test_query_traces_with_min_duration_param():
    """query_traces passes minDuration param when provided."""
    from backend.main import app
    body = {"traces": []}
    with patch.dict(os.environ, _TEMPO_ENV):
        with patch("httpx.AsyncClient", return_value=_mock_httpx(200, body)) as mock_cls:
            resp = TestClient(app).get(
                "/grafana/traces",
                params={"minDuration": "100ms"},
                headers=auth(),
            )
    assert resp.status_code == 200
    # Verify minDuration was forwarded in the request params
    call_kwargs = mock_cls.return_value.__aenter__.return_value.get.call_args
    params = call_kwargs.kwargs.get("params", call_kwargs.args[1] if len(call_kwargs.args) > 1 else {})
    assert params.get("minDuration") == "100ms"


def test_traces_batch_with_min_duration_param():
    """traces/batch passes minDuration when item includes it."""
    from backend.main import app
    body = {"traces": []}
    items = [{"minDuration": "200ms", "limit": 10}]
    with patch.dict(os.environ, _TEMPO_ENV):
        with patch("httpx.AsyncClient", return_value=_mock_httpx(200, body)):
            resp = TestClient(app).post("/grafana/traces/batch", json=items, headers=auth())
    assert resp.status_code == 200
    assert len(resp.json()) == 1
