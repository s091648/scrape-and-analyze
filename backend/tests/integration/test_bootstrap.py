"""
Integration tests for POST /bootstrap — collapses the SSR-initialization chain
(guest token + GET /topics + GET /languages) into a single unauthenticated round trip.
"""
import uuid

import pytest

pytestmark = pytest.mark.integration


def _seed_topic(db_session, name=None, is_active=True, sort_order=1):
    from models.topic import Topic
    t = Topic(
        id=uuid.uuid4(),
        name=name or f"seed-{uuid.uuid4().hex[:6]}",
        display_name="Seed Topic",
        color_hex="#123456",
        sort_order=sort_order,
        is_active=is_active,
    )
    db_session.add(t)
    db_session.flush()
    return t


def test_bootstrap_returns_guest_token_topics_and_languages(api_client, db_session):
    _seed_topic(db_session, name="bootstrap-topic")
    r = api_client.app_client.post("/bootstrap")
    assert r.status_code == 200
    data = r.json()
    assert data["access_token"]
    assert data["expires_in"] == 3600
    names = [t["name"] for t in data["topics"]]
    assert "bootstrap-topic" in names
    assert "available" in data["languages"]
    assert "resolved" in data["languages"]


def test_bootstrap_excludes_inactive_topics(api_client, db_session):
    _seed_topic(db_session, name="bootstrap-active", is_active=True)
    _seed_topic(db_session, name="bootstrap-inactive", is_active=False)
    r = api_client.app_client.post("/bootstrap")
    names = [t["name"] for t in r.json()["topics"]]
    assert "bootstrap-active" in names
    assert "bootstrap-inactive" not in names


def test_bootstrap_requires_no_authorization_header(api_client):
    r = api_client.app_client.post("/bootstrap")
    assert r.status_code == 200


def test_bootstrap_issued_guest_token_is_usable_against_other_endpoints(api_client):
    token = api_client.app_client.post("/bootstrap").json()["access_token"]
    r = api_client.app_client.get("/topics", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_bootstrap_shares_topics_cache_with_get_topics(api_client, db_session):
    _seed_topic(db_session, name="shared-cache-topic")
    first = api_client.app_client.post("/bootstrap")
    second = api_client.get("/topics")
    assert first.status_code == 200
    assert second.headers["X-Cache"] == "HIT"


def test_get_topics_then_bootstrap_is_also_a_shared_cache_hit(api_client, db_session):
    _seed_topic(db_session, name="shared-cache-topic-2")
    first = api_client.get("/topics")
    assert first.headers["X-Cache"] == "MISS"
    second = api_client.app_client.post("/bootstrap")
    names = [t["name"] for t in second.json()["topics"]]
    assert "shared-cache-topic-2" in names
