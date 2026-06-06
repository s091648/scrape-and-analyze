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


def test_middleware_sets_valid_uuid4_request_id():
    """Response X-Request-ID header must be a valid UUID4."""
    import uuid
    with patch("shared.utils.geoip.get_geo", return_value={}):
        client = TestClient(make_app())
        response = client.get("/")
    request_id = response.headers.get("x-request-id", "")
    parsed = uuid.UUID(request_id, version=4)
    assert str(parsed) == request_id
