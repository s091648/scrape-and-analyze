"""
Integration tests for /llm-providers CRUD endpoints.
All endpoints require admin JWT.
"""
import time
import uuid

import pytest
from jose import jwt

pytestmark = pytest.mark.integration


def admin_token() -> str:
    payload = {"sub": "admin", "role": "admin", "exp": int(time.time()) + 3600}
    return jwt.encode(payload, "test-secret", algorithm="HS256")


_ADMIN_HDR = {"Authorization": f"Bearer {admin_token()}"}

_PAYLOAD = {
    "name": "gemini",
    "model": "gemini-integration-test",
    "api_key_env": "GEMINI_API_KEY",
    "priority": 99,
    "is_active": True,
    "rpm": 5,
    "tpm": 250000,
    "rpd": 20,
}


def test_list_requires_admin(api_client):
    r = api_client.get("/llm-providers")
    assert r.status_code in (401, 403)


def test_create_requires_admin(api_client):
    r = api_client.post("/llm-providers", json=_PAYLOAD)
    assert r.status_code in (401, 403)


def test_create_persists(api_client):
    r = api_client.post("/llm-providers", json=_PAYLOAD, headers=_ADMIN_HDR)
    assert r.status_code == 201
    data = r.json()
    assert data["model"] == "gemini-integration-test"
    assert data["priority"] == 99
    assert "id" in data
    assert "usage_24h" in data


def test_create_appears_in_list(api_client):
    api_client.post("/llm-providers", json=_PAYLOAD, headers=_ADMIN_HDR)
    r = api_client.get("/llm-providers", headers=_ADMIN_HDR)
    assert r.status_code == 200
    models = [p["model"] for p in r.json()]
    assert "gemini-integration-test" in models


def test_update_persists(api_client):
    created = api_client.post("/llm-providers", json=_PAYLOAD, headers=_ADMIN_HDR).json()
    pid = created["id"]

    r = api_client.patch(f"/llm-providers/{pid}", json={"priority": 50}, headers=_ADMIN_HDR)
    assert r.status_code == 200
    assert r.json()["priority"] == 50


def test_update_is_active(api_client):
    created = api_client.post("/llm-providers", json=_PAYLOAD, headers=_ADMIN_HDR).json()
    pid = created["id"]

    r = api_client.patch(f"/llm-providers/{pid}", json={"is_active": False}, headers=_ADMIN_HDR)
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_update_nonexistent_returns_404(api_client):
    r = api_client.patch(f"/llm-providers/{uuid.uuid4()}", json={"priority": 1}, headers=_ADMIN_HDR)
    assert r.status_code == 404


def test_delete_removes_from_list(api_client):
    created = api_client.post("/llm-providers", json=_PAYLOAD, headers=_ADMIN_HDR).json()
    pid = created["id"]

    r = api_client.delete(f"/llm-providers/{pid}", headers=_ADMIN_HDR)
    assert r.status_code == 204

    remaining = [p["id"] for p in api_client.get("/llm-providers", headers=_ADMIN_HDR).json()]
    assert pid not in remaining


def test_delete_nonexistent_returns_404(api_client):
    r = api_client.delete(f"/llm-providers/{uuid.uuid4()}", headers=_ADMIN_HDR)
    assert r.status_code == 404


def test_full_cycle(api_client):
    created = api_client.post("/llm-providers", json=_PAYLOAD, headers=_ADMIN_HDR).json()
    pid = created["id"]

    updated = api_client.patch(f"/llm-providers/{pid}", json={"model": "gemini-cycle-updated"}, headers=_ADMIN_HDR).json()
    assert updated["model"] == "gemini-cycle-updated"

    api_client.delete(f"/llm-providers/{pid}", headers=_ADMIN_HDR)

    remaining = [p["id"] for p in api_client.get("/llm-providers", headers=_ADMIN_HDR).json()]
    assert pid not in remaining