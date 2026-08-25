import asyncio

import pytest
from unittest.mock import patch, MagicMock

from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import PlainTextResponse


async def homepage(request):
    return PlainTextResponse("ok")


def make_app():
    from backend.middleware.logging import RequestLoggingMiddleware
    app = Starlette(routes=[Route("/", homepage)])
    app.add_middleware(RequestLoggingMiddleware)
    return app


def test_middleware_adds_x_request_id_header():
    client = TestClient(make_app())
    response = client.get("/")
    assert "x-request-id" in response.headers


def test_middleware_returns_200():
    client = TestClient(make_app())
    response = client.get("/")
    assert response.status_code == 200


def test_middleware_logs_ip_and_user_agent():
    """Enriched middleware must log ip and user_agent fields."""
    with patch("backend.middleware.logging.logger") as mock_logger, \
         patch("shared.utils.geoip.get_geo", return_value={}):
        client = TestClient(make_app())
        client.get("/", headers={"User-Agent": "TestBrowser/1.0"})
    kwargs = mock_logger.info.call_args.kwargs
    assert "ip" in kwargs
    assert "user_agent" in kwargs


def test_middleware_logs_geo_fields_when_available():
    """When GeoIP lookup returns country/city, they must appear in the log."""
    with patch("backend.middleware.logging.logger") as mock_logger, \
         patch("shared.utils.geoip.get_geo", return_value={"country": "TW", "city": "Taipei"}):
        client = TestClient(make_app())
        client.get("/")
    kwargs = mock_logger.info.call_args.kwargs
    assert "geo_country" in kwargs
    assert "geo_city" in kwargs


def test_middleware_logs_anonymous_when_no_auth():
    """Requests without Authorization header must log user_id as anonymous."""
    with patch("backend.middleware.logging.logger") as mock_logger, \
         patch("shared.utils.geoip.get_geo", return_value={}):
        client = TestClient(make_app())
        client.get("/")
    kwargs = mock_logger.info.call_args.kwargs
    assert kwargs.get("user_id") == "anonymous"


def test_middleware_logs_user_identity_when_authenticated():
    """Authenticated requests must log user_id, user_email, and user_role."""
    from jose import jwt as jose_jwt
    secret = "test-secret-for-middleware"
    token = jose_jwt.encode(
        {"sub": "user-42", "email": "a@b.com", "role": "admin"},
        secret,
        algorithm="HS256",
    )
    with patch("backend.middleware.logging.logger") as mock_logger, \
         patch("backend.middleware.logging._SECRET", secret), \
         patch("shared.utils.geoip.get_geo", return_value={}):
        client = TestClient(make_app())
        client.get("/", headers={"Authorization": f"Bearer {token}"})
    kwargs = mock_logger.info.call_args.kwargs
    assert kwargs.get("user_id") == "user-42"
    assert kwargs.get("user_email") == "a@b.com"
    assert kwargs.get("user_role") == "admin"


def test_middleware_logs_duration_ms():
    """The duration_ms field must be present and non-negative in the log."""
    with patch("backend.middleware.logging.logger") as mock_logger, \
         patch("shared.utils.geoip.get_geo", return_value={}):
        client = TestClient(make_app())
        client.get("/")
    kwargs = mock_logger.info.call_args.kwargs
    assert "duration_ms" in kwargs
    assert kwargs["duration_ms"] >= 0


def test_middleware_logs_query_params():
    with patch("backend.middleware.logging.logger") as mock_logger, \
         patch("shared.utils.geoip.get_geo", return_value={}):
        client = TestClient(make_app())
        client.get("/?lang=zh-TW&limit=10")
    kwargs = mock_logger.info.call_args.kwargs
    assert kwargs.get("query_params") == "lang=zh-TW&limit=10"


def test_middleware_omits_query_params_when_absent():
    with patch("backend.middleware.logging.logger") as mock_logger, \
         patch("shared.utils.geoip.get_geo", return_value={}):
        client = TestClient(make_app())
        client.get("/")
    kwargs = mock_logger.info.call_args.kwargs
    assert "query_params" not in kwargs


def test_middleware_logs_json_payload():
    import json as _json

    async def echo_body(request):
        await request.body()
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/echo", echo_body, methods=["POST"])])
    from backend.middleware.logging import RequestLoggingMiddleware
    app.add_middleware(RequestLoggingMiddleware)

    with patch("backend.middleware.logging.logger") as mock_logger, \
         patch("shared.utils.geoip.get_geo", return_value={}):
        client = TestClient(app)
        client.post("/echo", json={"topic": "llm", "limit": 5})
    kwargs = mock_logger.info.call_args.kwargs
    assert _json.loads(kwargs["payload"]) == {"topic": "llm", "limit": 5}


def test_middleware_redacts_sensitive_payload_fields():
    async def echo_body(request):
        await request.body()
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/echo", echo_body, methods=["POST"])])
    from backend.middleware.logging import RequestLoggingMiddleware
    app.add_middleware(RequestLoggingMiddleware)

    with patch("backend.middleware.logging.logger") as mock_logger, \
         patch("shared.utils.geoip.get_geo", return_value={}):
        client = TestClient(app)
        client.post("/echo", json={"username": "alice", "password": "hunter2"})
    kwargs = mock_logger.info.call_args.kwargs
    assert '"password": "***"' in kwargs["payload"]
    assert "hunter2" not in kwargs["payload"]
    assert '"username": "alice"' in kwargs["payload"]


def test_middleware_omits_payload_for_non_json_body():
    async def echo_body(request):
        await request.body()
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/echo", echo_body, methods=["POST"])])
    from backend.middleware.logging import RequestLoggingMiddleware
    app.add_middleware(RequestLoggingMiddleware)

    with patch("backend.middleware.logging.logger") as mock_logger, \
         patch("shared.utils.geoip.get_geo", return_value={}):
        client = TestClient(app)
        client.post("/echo", content=b"plain text body", headers={"Content-Type": "text/plain"})
    kwargs = mock_logger.info.call_args.kwargs
    assert "payload" not in kwargs


def test_middleware_sets_valid_uuid4_request_id():
    """Response X-Request-ID header must be a valid UUID4."""
    import uuid
    with patch("shared.utils.geoip.get_geo", return_value={}):
        client = TestClient(make_app())
        response = client.get("/")
    request_id = response.headers.get("x-request-id", "")
    parsed = uuid.UUID(request_id, version=4)
    assert str(parsed) == request_id


# ── Streaming pass-through (regression) ─────────────────────────────────────────
# This middleware is deliberately pure ASGI, not starlette.middleware.base.BaseHTTPMiddleware —
# BaseHTTPMiddleware relays the downstream response through an internal buffer to hand dispatch()
# a single Response object, which collapses a StreamingResponse (see /chat/completions) into one
# burst delivered only once generation has fully finished, instead of the client watching content
# arrive live as the LLM streams it. These tests exercise the ASGI interface directly (no
# TestClient, which itself doesn't distinguish incremental vs. buffered delivery) to prove each
# chunk is forwarded through `send` as the downstream app produces it.

@pytest.mark.asyncio
async def test_middleware_forwards_streamed_chunks_as_they_are_produced():
    from backend.middleware.logging import RequestLoggingMiddleware

    progress: list[str] = []

    async def streaming_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        for i in range(3):
            progress.append(f"producing-{i}")
            await send({"type": "http.response.body", "body": f"chunk-{i}".encode(), "more_body": True})
            progress.append(f"produced-{i}")
            await asyncio.sleep(0)  # yields control, as real async work between chunks would
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    middleware = RequestLoggingMiddleware(streaming_app)

    received: list[bytes] = []

    async def fake_send(message):
        if message["type"] == "http.response.body" and message.get("body"):
            received.append(message["body"])
            # The middleware forwards this chunk synchronously, inline with the app's own
            # `await send(...)` call — so at the moment it's observed here, the app hasn't even
            # reached its own "produced-N" bookkeeping yet (the next line after that await).
            # Proves each chunk reaches the client as it's made, not batched until the app —
            # and by extension the whole LLM generation — finishes (which "produced-2" already
            # being in `progress` by the time chunk 0 is observed here would indicate).
            assert progress[-1] == f"producing-{len(received) - 1}"

    async def fake_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("127.0.0.1", 1234)}

    with patch("shared.utils.geoip.get_geo", return_value={}):
        await middleware(scope, fake_receive, fake_send)

    assert received == [b"chunk-0", b"chunk-1", b"chunk-2"]


@pytest.mark.asyncio
async def test_middleware_still_adds_request_id_header_for_streaming_responses():
    from backend.middleware.logging import RequestLoggingMiddleware

    async def streaming_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"chunk", "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    middleware = RequestLoggingMiddleware(streaming_app)
    start_message = {}

    async def fake_send(message):
        if message["type"] == "http.response.start":
            start_message.update(message)

    async def fake_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("127.0.0.1", 1234)}

    with patch("shared.utils.geoip.get_geo", return_value={}):
        await middleware(scope, fake_receive, fake_send)

    header_names = [k for k, _ in start_message.get("headers", [])]
    assert b"x-request-id" in header_names
