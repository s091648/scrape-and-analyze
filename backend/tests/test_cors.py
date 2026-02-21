import os
from unittest.mock import patch


def test_cors_allowed_origin():
    os.environ["FRONTEND_ORIGIN"] = "http://localhost:3000"
    from backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"}
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_blocked_origin():
    os.environ["FRONTEND_ORIGIN"] = "http://localhost:3000"
    from backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={"Origin": "http://evil.com", "Access-Control-Request-Method": "GET"}
    )
    assert response.headers.get("access-control-allow-origin") != "http://evil.com"
