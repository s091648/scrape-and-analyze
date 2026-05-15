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
