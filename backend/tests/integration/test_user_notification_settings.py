"""Integration tests for GET/PUT /user/notification-settings."""
import uuid
import time

import pytest
from jose import jwt

pytestmark = pytest.mark.integration

_JWT_SECRET = "test-secret"

_USER_IDS = {
    "new": "00000000-0000-0000-0000-000000000021",
    "existing": "00000000-0000-0000-0000-000000000022",
    "partial": "00000000-0000-0000-0000-000000000023",
}


def _user_token(user_key: str) -> str:
    user_id = _USER_IDS[user_key]
    payload = {"sub": user_id, "role": "user", "exp": int(time.time()) + 3600}
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def _seed_user(db_session, user_key: str):
    from models.auth import User

    user_id = uuid.UUID(_USER_IDS[user_key])
    if db_session.get(User, user_id) is None:
        db_session.add(User(id=user_id, role="user", email=f"{user_key}@example.com"))
        db_session.flush()


# ─── GET /user/notification-settings ─────────────────────────────────────────

def test_get_requires_auth(api_client):
    r = api_client.get("/user/notification-settings")
    assert r.status_code == 401


def test_get_returns_defaults_for_user_with_no_settings_row(db_session, api_client):
    _seed_user(db_session, "new")
    token = _user_token("new")
    r = api_client.get("/user/notification-settings", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["email_enabled"] is True
    assert data["telegram_chat_id"] is None
    assert data["telegram_enabled"] is False
    assert data["locale"] == "en"


# ─── PUT /user/notification-settings ─────────────────────────────────────────

def test_put_creates_settings_row_when_none_exists(db_session, api_client):
    _seed_user(db_session, "new")
    token = _user_token("new")
    headers = {"Authorization": f"Bearer {token}"}

    r = api_client.put(
        "/user/notification-settings",
        json={"email_enabled": False, "telegram_chat_id": "12345", "telegram_enabled": True, "locale": "zh-TW"},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["email_enabled"] is False
    assert data["telegram_chat_id"] == "12345"
    assert data["telegram_enabled"] is True
    assert data["locale"] == "zh-TW"


def test_put_create_uses_defaults_for_omitted_fields(db_session, api_client):
    _seed_user(db_session, "partial")
    token = _user_token("partial")
    headers = {"Authorization": f"Bearer {token}"}

    r = api_client.put("/user/notification-settings", json={}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["email_enabled"] is True
    assert data["telegram_enabled"] is False
    assert data["locale"] == "en"
    assert data["telegram_chat_id"] is None


def test_put_updates_existing_settings_row(db_session, api_client):
    _seed_user(db_session, "existing")
    token = _user_token("existing")
    headers = {"Authorization": f"Bearer {token}"}

    api_client.put(
        "/user/notification-settings",
        json={"email_enabled": True, "telegram_enabled": False, "locale": "en"},
        headers=headers,
    )

    r = api_client.put(
        "/user/notification-settings",
        json={"telegram_enabled": True, "telegram_chat_id": "999"},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["telegram_enabled"] is True
    assert data["telegram_chat_id"] == "999"
    # Field left out of the second PUT keeps its previously-set value.
    assert data["email_enabled"] is True


def test_put_persists_across_subsequent_get(db_session, api_client):
    _seed_user(db_session, "existing")
    token = _user_token("existing")
    headers = {"Authorization": f"Bearer {token}"}

    api_client.put(
        "/user/notification-settings",
        json={"locale": "zh-TW"},
        headers=headers,
    )

    r = api_client.get("/user/notification-settings", headers=headers)
    assert r.json()["locale"] == "zh-TW"


def test_put_requires_auth(api_client):
    r = api_client.put("/user/notification-settings", json={"locale": "en"})
    assert r.status_code == 401
