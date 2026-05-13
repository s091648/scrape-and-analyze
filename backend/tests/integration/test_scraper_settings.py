"""
Integration tests for /scraper-settings CRUD endpoints.

Unit tests mock all DB calls.  These tests verify that create/update/delete
operations actually persist and that 404 is raised for missing IDs.
All endpoints require admin JWT.
"""
import uuid

import pytest

from backend.tests.integration.conftest import admin_token

pytestmark = pytest.mark.integration

_ADMIN_HDR = {"Authorization": f"Bearer {admin_token()}"}

_RSS_PAYLOAD = {
    "source_type": "rss",
    "name": "Test Feed",
    "url": "https://example.com/feed.xml",
    "frequency": 60,
    "is_active": True,
    "topic_id": str(uuid.uuid4()),
}


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def test_list_settings_requires_admin(api_client):
    r = api_client.get("/scraper-settings")
    assert r.status_code in (401, 403)


def test_create_setting_requires_admin(api_client):
    r = api_client.post("/scraper-settings", json=_RSS_PAYLOAD)
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def test_create_setting_persists(api_client):
    r = api_client.post("/scraper-settings", json=_RSS_PAYLOAD, headers=_ADMIN_HDR)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Test Feed"
    assert data["source_type"] == "rss"
    assert "id" in data


def test_create_setting_appears_in_list(api_client):
    api_client.post("/scraper-settings", json=_RSS_PAYLOAD, headers=_ADMIN_HDR)

    r = api_client.get("/scraper-settings", headers=_ADMIN_HDR)
    assert r.status_code == 200
    names = [s["name"] for s in r.json()]
    assert "Test Feed" in names


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def test_update_setting_persists(api_client):
    created = api_client.post("/scraper-settings", json=_RSS_PAYLOAD,
                              headers=_ADMIN_HDR).json()
    sid = created["id"]

    r = api_client.patch(f"/scraper-settings/{sid}",
                         json={"name": "Updated Feed"},
                         headers=_ADMIN_HDR)
    assert r.status_code == 200
    assert r.json()["name"] == "Updated Feed"


def test_update_setting_frequency(api_client):
    created = api_client.post("/scraper-settings", json=_RSS_PAYLOAD,
                              headers=_ADMIN_HDR).json()
    sid = created["id"]

    r = api_client.patch(f"/scraper-settings/{sid}",
                         json={"frequency": 120},
                         headers=_ADMIN_HDR)
    assert r.status_code == 200
    assert r.json()["frequency"] == 120


def test_update_nonexistent_returns_404(api_client):
    r = api_client.patch(f"/scraper-settings/{uuid.uuid4()}",
                         json={"name": "Ghost"},
                         headers=_ADMIN_HDR)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def test_delete_setting_removes_from_list(api_client):
    created = api_client.post("/scraper-settings", json=_RSS_PAYLOAD,
                              headers=_ADMIN_HDR).json()
    sid = created["id"]

    r = api_client.delete(f"/scraper-settings/{sid}", headers=_ADMIN_HDR)
    assert r.status_code == 204

    settings = api_client.get("/scraper-settings", headers=_ADMIN_HDR).json()
    assert all(s["id"] != sid for s in settings)


def test_delete_nonexistent_returns_404(api_client):
    r = api_client.delete(f"/scraper-settings/{uuid.uuid4()}", headers=_ADMIN_HDR)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Full cycle
# ---------------------------------------------------------------------------

def test_create_update_delete_cycle(api_client):
    # Create
    created = api_client.post("/scraper-settings", json=_RSS_PAYLOAD,
                              headers=_ADMIN_HDR).json()
    sid = created["id"]

    # Update
    updated = api_client.patch(f"/scraper-settings/{sid}",
                               json={"name": "Cycle Feed"},
                               headers=_ADMIN_HDR).json()
    assert updated["name"] == "Cycle Feed"

    # Confirm in list
    names = [s["name"] for s in
             api_client.get("/scraper-settings", headers=_ADMIN_HDR).json()]
    assert "Cycle Feed" in names

    # Delete
    api_client.delete(f"/scraper-settings/{sid}", headers=_ADMIN_HDR)

    # Confirm removed
    names_after = [s["name"] for s in
                   api_client.get("/scraper-settings", headers=_ADMIN_HDR).json()]
    assert "Cycle Feed" not in names_after
