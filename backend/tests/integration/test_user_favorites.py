"""Integration tests for /user/favorites and GET /articles?favorites_only=true."""
import uuid
import time
from datetime import datetime, timezone

import pytest
from jose import jwt

pytestmark = pytest.mark.integration

_JWT_SECRET = "test-secret"

_USER_IDS = {
    "new": "00000000-0000-0000-0000-000000000001",
    "fav001": "00000000-0000-0000-0000-000000000011",
    "fav002": "00000000-0000-0000-0000-000000000012",
    "fav003": "00000000-0000-0000-0000-000000000013",
    "fav004": "00000000-0000-0000-0000-000000000014",
    "fav005": "00000000-0000-0000-0000-000000000015",
    "fav006": "00000000-0000-0000-0000-000000000016",
    "anon": "00000000-0000-0000-0000-000000000099",
}


def _user_token(user_key: str) -> str:
    user_id = _USER_IDS[user_key]
    payload = {"sub": user_id, "role": "user", "exp": int(time.time()) + 3600}
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def _seed_user(db_session, user_key: str):
    """Rows written under user_id FKs (favorites) require a real auth.users row.
    Inserted via db_session so it rolls back with the rest of the test's transaction."""
    from models.auth import User

    user_id = uuid.UUID(_USER_IDS[user_key])
    if db_session.get(User, user_id) is None:
        db_session.add(User(id=user_id, role="user", email=f"{user_key}@example.com"))
        db_session.flush()


def _article(source="arxiv", title="Test"):
    from models.article import Article
    return Article(
        id=uuid.uuid4(),
        url=f"https://example.com/{uuid.uuid4().hex}",
        url_hash=uuid.uuid4().hex,
        source=source,
        title=title,
        content="body",
        correlation_id=uuid.uuid4(),
        scraped_at=datetime.now(timezone.utc),
    )


# ─── GET /user/favorites ─────────────────────────────────────────────────────

def test_get_favorites_returns_empty_for_new_user(api_client):
    token = _user_token("new")
    r = api_client.get("/user/favorites", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["article_ids"] == []


def test_get_favorites_requires_auth(api_client):
    r = api_client.get("/user/favorites")
    assert r.status_code == 401


# ─── POST /user/favorites/{article_id} ───────────────────────────────────────

def test_add_favorite_returns_201(db_session, api_client):
    article = _article()
    db_session.add(article)
    _seed_user(db_session, "fav001")

    token = _user_token("fav001")
    r = api_client.post(f"/user/favorites/{article.id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201


def test_add_favorite_appears_in_get(db_session, api_client):
    article = _article()
    db_session.add(article)
    _seed_user(db_session, "fav002")

    token = _user_token("fav002")
    headers = {"Authorization": f"Bearer {token}"}
    api_client.post(f"/user/favorites/{article.id}", headers=headers)

    r = api_client.get("/user/favorites", headers=headers)
    assert str(article.id) in r.json()["article_ids"]


def test_add_favorite_is_idempotent(db_session, api_client):
    article = _article()
    db_session.add(article)
    _seed_user(db_session, "fav003")

    token = _user_token("fav003")
    headers = {"Authorization": f"Bearer {token}"}
    api_client.post(f"/user/favorites/{article.id}", headers=headers)
    r2 = api_client.post(f"/user/favorites/{article.id}", headers=headers)
    assert r2.status_code in (201, 204)

    r = api_client.get("/user/favorites", headers=headers)
    assert r.json()["article_ids"].count(str(article.id)) == 1


# ─── DELETE /user/favorites/{article_id} ─────────────────────────────────────

def test_remove_favorite_returns_204(db_session, api_client):
    article = _article()
    db_session.add(article)
    _seed_user(db_session, "fav004")

    token = _user_token("fav004")
    headers = {"Authorization": f"Bearer {token}"}
    api_client.post(f"/user/favorites/{article.id}", headers=headers)

    r = api_client.delete(f"/user/favorites/{article.id}", headers=headers)
    assert r.status_code == 204


def test_remove_favorite_disappears_from_list(db_session, api_client):
    article = _article()
    db_session.add(article)
    _seed_user(db_session, "fav005")

    token = _user_token("fav005")
    headers = {"Authorization": f"Bearer {token}"}
    api_client.post(f"/user/favorites/{article.id}", headers=headers)
    api_client.delete(f"/user/favorites/{article.id}", headers=headers)

    r = api_client.get("/user/favorites", headers=headers)
    assert str(article.id) not in r.json()["article_ids"]


# ─── GET /articles?favorites_only=true ───────────────────────────────────────

def test_favorites_only_filter_returns_only_favorited_articles(db_session, api_client):
    fav_article = _article(title="Favorited")
    other_article = _article(title="Other")
    db_session.add(fav_article)
    db_session.add(other_article)
    _seed_user(db_session, "fav006")

    token = _user_token("fav006")
    headers = {"Authorization": f"Bearer {token}"}
    api_client.post(f"/user/favorites/{fav_article.id}", headers=headers)

    r = api_client.get("/articles?favorites_only=true", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Favorited"


def test_favorites_only_returns_empty_for_unauthenticated(db_session, api_client):
    article = _article()
    db_session.add(article)
    db_session.flush()

    r = api_client.get("/articles?favorites_only=true")
    assert r.status_code == 200
    assert r.json()["total"] == 0
