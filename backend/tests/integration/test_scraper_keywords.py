"""
Integration tests for /scraper-keywords CRUD endpoints.

backend/tests/test_scraper_keywords.py mocks the DB session entirely. These
tests verify create/list/delete actually persist against a real Postgres
`collection.scraper_keywords` row (FK'd to a real `core.topics` row) and that
the (topic_id, keyword_type, keyword) uniqueness rule is enforced for real.
"""
import uuid

import pytest

from backend.tests.integration.conftest import admin_token

pytestmark = pytest.mark.integration

_ADMIN_HDR = {"Authorization": f"Bearer {admin_token()}"}


def _seed_topic(db_session, name=None):
    from models.topic import Topic
    t = Topic(
        id=uuid.uuid4(),
        name=name or f"topic-{uuid.uuid4().hex[:6]}",
        display_name="Seed Topic",
        color_hex="#123456",
        sort_order=1,
        is_active=True,
    )
    db_session.add(t)
    db_session.flush()
    return t


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def test_list_keywords_requires_admin(api_client, db_session):
    topic = _seed_topic(db_session)
    r = api_client.app_client.get(f"/scraper-keywords?topic_id={topic.id}")
    assert r.status_code == 401


def test_create_keyword_requires_admin(api_client, db_session):
    topic = _seed_topic(db_session)
    r = api_client.app_client.post(
        f"/scraper-keywords?topic_id={topic.id}", json={"keyword": "ai"}
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Create / list
# ---------------------------------------------------------------------------

def test_create_keyword_persists(api_client, db_session):
    topic = _seed_topic(db_session)

    r = api_client.post(
        f"/scraper-keywords?topic_id={topic.id}",
        json={"keyword": "digital twin", "keyword_type": "rss"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["keyword"] == "digital twin"
    assert data["keyword_type"] == "rss"

    from models.scraper_keyword import ScraperKeyword
    row = db_session.query(ScraperKeyword).filter(ScraperKeyword.id == uuid.UUID(data["id"])).first()
    assert row is not None
    assert row.topic_id == topic.id


def test_create_keyword_appears_in_list(api_client, db_session):
    topic = _seed_topic(db_session)
    api_client.post(
        f"/scraper-keywords?topic_id={topic.id}",
        json={"keyword": "arxiv-kw", "keyword_type": "arxiv_keyword"},
        headers=_ADMIN_HDR,
    )

    r = api_client.get(f"/scraper-keywords?topic_id={topic.id}", headers=_ADMIN_HDR)
    assert r.status_code == 200
    keywords = [k["keyword"] for k in r.json()]
    assert "arxiv-kw" in keywords


def test_list_keywords_filters_by_keyword_type(api_client, db_session):
    topic = _seed_topic(db_session)
    api_client.post(
        f"/scraper-keywords?topic_id={topic.id}",
        json={"keyword": "rss-kw", "keyword_type": "rss"},
        headers=_ADMIN_HDR,
    )
    api_client.post(
        f"/scraper-keywords?topic_id={topic.id}",
        json={"keyword": "category-kw", "keyword_type": "arxiv_category"},
        headers=_ADMIN_HDR,
    )

    r = api_client.get(
        f"/scraper-keywords?topic_id={topic.id}&keyword_type=arxiv_category",
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    keywords = [k["keyword"] for k in r.json()]
    assert keywords == ["category-kw"]


def test_create_keyword_invalid_type_returns_422(api_client, db_session):
    topic = _seed_topic(db_session)
    r = api_client.post(
        f"/scraper-keywords?topic_id={topic.id}",
        json={"keyword": "bad-type", "keyword_type": "not-a-real-type"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 422


def test_create_duplicate_keyword_returns_409(api_client, db_session):
    topic = _seed_topic(db_session)
    payload = {"keyword": "dup-keyword", "keyword_type": "rss"}
    api_client.post(f"/scraper-keywords?topic_id={topic.id}", json=payload, headers=_ADMIN_HDR)

    r = api_client.post(f"/scraper-keywords?topic_id={topic.id}", json=payload, headers=_ADMIN_HDR)
    assert r.status_code == 409


def test_same_keyword_allowed_under_different_topics(api_client, db_session):
    topic_a = _seed_topic(db_session)
    topic_b = _seed_topic(db_session)
    payload = {"keyword": "shared-keyword", "keyword_type": "rss"}

    r1 = api_client.post(f"/scraper-keywords?topic_id={topic_a.id}", json=payload, headers=_ADMIN_HDR)
    r2 = api_client.post(f"/scraper-keywords?topic_id={topic_b.id}", json=payload, headers=_ADMIN_HDR)
    assert r1.status_code == 201
    assert r2.status_code == 201


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def test_delete_keyword_removes_row(api_client, db_session):
    topic = _seed_topic(db_session)
    created = api_client.post(
        f"/scraper-keywords?topic_id={topic.id}",
        json={"keyword": "to-delete", "keyword_type": "rss"},
        headers=_ADMIN_HDR,
    ).json()

    r = api_client.delete(f"/scraper-keywords/{created['id']}", headers=_ADMIN_HDR)
    assert r.status_code == 204

    from models.scraper_keyword import ScraperKeyword
    assert db_session.query(ScraperKeyword).filter(ScraperKeyword.id == uuid.UUID(created["id"])).first() is None


def test_delete_keyword_not_found_returns_404(api_client):
    r = api_client.delete(f"/scraper-keywords/{uuid.uuid4()}", headers=_ADMIN_HDR)
    assert r.status_code == 404


def test_delete_keyword_requires_admin(api_client, db_session):
    topic = _seed_topic(db_session)
    created = api_client.post(
        f"/scraper-keywords?topic_id={topic.id}",
        json={"keyword": "guarded", "keyword_type": "rss"},
        headers=_ADMIN_HDR,
    ).json()

    r = api_client.app_client.delete(f"/scraper-keywords/{created['id']}")
    assert r.status_code == 401
