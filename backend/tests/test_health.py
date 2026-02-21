import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import OperationalError


def test_health_returns_200():
    from backend.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_health_db_ok():
    from backend.main import app
    client = TestClient(app)
    with patch("backend.main.check_db_connection", return_value=True):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["db"] == "ok"


def test_health_db_down():
    from backend.main import app
    client = TestClient(app)
    with patch("backend.main.check_db_connection", return_value=False):
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["db"] == "error"
