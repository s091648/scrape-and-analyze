"""
Integration tests for /topics endpoints.

Tests use a real PostgreSQL schema (backend_test) with per-test rollback.
Topic model is registered in the test schema via conftest.db_engine.
"""
import uuid

import pytest

from backend.tests.integration.conftest import admin_token

pytestmark = pytest.mark.integration

_ADMIN_HDR = {"Authorization": f"Bearer {admin_token()}"}
_USER_HDR = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
             "eyJzdWIiOiJ1c2VyMSIsInJvbGUiOiJ1c2VyIiwiZXhwIjo5OTk5OTk5OTk5fQ."
             "INVALID"}  # JWT with role=user (signed differently → will be rejected as 401)


def _topic_payload(**kwargs):
    name = kwargs.get("name", f"topic-{uuid.uuid4().hex[:6]}")
    return {
        "name": name,
        "display_name": kwargs.get("display_name", name.replace("-", " ").title()),
        **{k: v for k, v in kwargs.items() if k not in ("name", "display_name")},
    }


def _seed_topic(db_session, name=None, is_active=True):
    from models.topic import Topic
    t = Topic(
        id=uuid.uuid4(),
        name=name or f"seed-{uuid.uuid4().hex[:6]}",
        display_name="Seed Topic",
        color_hex="#123456",
        sort_order=1,
        is_active=is_active,
    )
    db_session.add(t)
    db_session.flush()
    return t


# ---------------------------------------------------------------------------
# GET /topics — public list
# ---------------------------------------------------------------------------

def test_list_topics_empty(api_client):
    r = api_client.get("/topics")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_topics_returns_active_only(api_client, db_session):
    _seed_topic(db_session, name="active-topic", is_active=True)
    _seed_topic(db_session, name="inactive-topic", is_active=False)

    r = api_client.get("/topics")
    assert r.status_code == 200
    names = [t["name"] for t in r.json()]
    assert "active-topic" in names
    assert "inactive-topic" not in names


def test_list_topics_include_inactive(api_client, db_session):
    _seed_topic(db_session, name="active-inc", is_active=True)
    _seed_topic(db_session, name="inactive-inc", is_active=False)

    r = api_client.get("/topics?include_inactive=true")
    assert r.status_code == 200
    names = [t["name"] for t in r.json()]
    assert "active-inc" in names
    assert "inactive-inc" in names


def test_list_topics_no_auth_required(api_client):
    r = api_client.get("/topics")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# POST /topics — requires admin
# ---------------------------------------------------------------------------

def test_create_topic_requires_auth(api_client):
    r = api_client.post("/topics", json=_topic_payload())
    assert r.status_code == 401


def test_create_topic_success(api_client):
    payload = _topic_payload(name="new-test-topic")
    r = api_client.post("/topics", json=payload, headers=_ADMIN_HDR)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "new-test-topic"
    assert "id" in data
    assert data["is_active"] is True


def test_create_topic_appears_in_list(api_client):
    name = f"list-check-{uuid.uuid4().hex[:6]}"
    api_client.post("/topics", json=_topic_payload(name=name), headers=_ADMIN_HDR)

    r = api_client.get("/topics")
    names = [t["name"] for t in r.json()]
    assert name in names


# ---------------------------------------------------------------------------
# PATCH /topics/{id} — requires admin
# ---------------------------------------------------------------------------

def test_update_topic_requires_auth(api_client, db_session):
    t = _seed_topic(db_session)
    r = api_client.patch(f"/topics/{t.id}", json={"display_name": "New Name"})
    assert r.status_code == 401


def test_update_topic_success(api_client, db_session):
    t = _seed_topic(db_session, name="patch-topic")
    r = api_client.patch(
        f"/topics/{t.id}",
        json={"display_name": "Updated Display", "color_hex": "#abcdef"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["display_name"] == "Updated Display"
    assert data["color_hex"] == "#abcdef"


def test_update_topic_not_found(api_client):
    r = api_client.patch(
        f"/topics/{uuid.uuid4()}",
        json={"display_name": "X"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /topics/{id} — soft delete (sets is_active=False)
# ---------------------------------------------------------------------------

def test_delete_topic_requires_auth(api_client, db_session):
    t = _seed_topic(db_session)
    r = api_client.delete(f"/topics/{t.id}")
    assert r.status_code == 401


def test_delete_topic_soft_deletes(api_client, db_session):
    t = _seed_topic(db_session, name="to-delete-topic", is_active=True)
    r = api_client.delete(f"/topics/{t.id}", headers=_ADMIN_HDR)
    assert r.status_code == 204

    # Topic no longer in active list
    names = [item["name"] for item in api_client.get("/topics").json()]
    assert "to-delete-topic" not in names

    # But present with include_inactive
    all_names = [item["name"] for item in api_client.get("/topics?include_inactive=true").json()]
    assert "to-delete-topic" in all_names


def test_delete_topic_not_found(api_client):
    r = api_client.delete(f"/topics/{uuid.uuid4()}", headers=_ADMIN_HDR)
    assert r.status_code == 404
