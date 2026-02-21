import pytest
from fastapi.testclient import TestClient


def test_health_returns_200():
    from backend.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
