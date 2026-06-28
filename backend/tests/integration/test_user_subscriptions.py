"""Integration tests for /user/subscriptions and /user/notification-settings."""
import uuid
import time
from datetime import datetime, timezone

import pytest
from jose import jwt

pytestmark = pytest.mark.integration

_JWT_SECRET = "test-secret"

_USER_IDS = {
    "sub001": "00000000-0000-0000-0000-000000000021",
    "sub002": "00000000-0000-0000-0000-000000000022",
    "sub003": "00000000-0000-0000-0000-000000000023",
    "sub004": "00000000-0000-0000-0000-000000000024",
    "notif001": "00000000-0000-0000-0000-000000000031",
    "notif002": "00000000-0000-0000-0000-000000000032",
    "notif003": "00000000-0000-0000-0000-000000000033",
}


def _user_token(user_key: str) -> str:
    user_id = _USER_IDS[user_key]
    payload = {"sub": user_id, "role": "user", "exp": int(time.time()) + 3600}
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def _topic(db_session):
    from models.topic import Topic
    topic = Topic(
        id=uuid.uuid4(),
        name=f"topic-{uuid.uuid4().hex[:8]}",
        display_name="Test Topic",
        is_active=True,
        tag_mode="unsupervised",
    )
    db_session.add(topic)
    db_session.flush()
    return topic


# ─── Subscriptions ────────────────────────────────────────────────────────────

def test_get_subscriptions_returns_empty_for_new_user(api_client):
    token = _user_token("sub001")
    r = api_client.get("/user/subscriptions", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["topic_ids"] == []


def test_get_subscriptions_requires_auth(api_client):
    r = api_client.get("/user/subscriptions")
    assert r.status_code == 401


def test_post_subscription_creates_row(db_session, api_client):
    topic = _topic(db_session)
    token = _user_token("sub002")
    headers = {"Authorization": f"Bearer {token}"}

    r = api_client.post(
        "/user/subscriptions",
        json={"topic_id": str(topic.id)},
        headers=headers,
    )
    assert r.status_code == 201

    r2 = api_client.get("/user/subscriptions", headers=headers)
    assert str(topic.id) in r2.json()["topic_ids"]


def test_post_subscription_is_idempotent(db_session, api_client):
    topic = _topic(db_session)
    token = _user_token("sub003")
    headers = {"Authorization": f"Bearer {token}"}

    api_client.post("/user/subscriptions", json={"topic_id": str(topic.id)}, headers=headers)
    r2 = api_client.post("/user/subscriptions", json={"topic_id": str(topic.id)}, headers=headers)
    assert r2.status_code in (201, 204)

    r = api_client.get("/user/subscriptions", headers=headers)
    assert r.json()["topic_ids"].count(str(topic.id)) == 1


def test_delete_subscription_removes_row(db_session, api_client):
    topic = _topic(db_session)
    token = _user_token("sub004")
    headers = {"Authorization": f"Bearer {token}"}

    api_client.post("/user/subscriptions", json={"topic_id": str(topic.id)}, headers=headers)
    r = api_client.delete(f"/user/subscriptions/{topic.id}", headers=headers)
    assert r.status_code == 204

    r2 = api_client.get("/user/subscriptions", headers=headers)
    assert str(topic.id) not in r2.json()["topic_ids"]


# ─── Notification Settings ────────────────────────────────────────────────────

def test_get_notification_settings_returns_defaults(api_client):
    token = _user_token("notif001")
    r = api_client.get("/user/notification-settings", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["email_enabled"], bool)
    assert data["telegram_enabled"] is False
    assert data["telegram_chat_id"] is None
    assert data["locale"] == "en"


def test_put_notification_settings_upserts(api_client):
    token = _user_token("notif002")
    headers = {"Authorization": f"Bearer {token}"}

    r = api_client.put(
        "/user/notification-settings",
        json={"email_enabled": True, "locale": "zh-TW"},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["email_enabled"] is True
    assert data["locale"] == "zh-TW"


def test_put_notification_settings_is_idempotent(api_client):
    token = _user_token("notif003")
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"telegram_enabled": True, "telegram_chat_id": "12345"}

    api_client.put("/user/notification-settings", json=payload, headers=headers)
    r2 = api_client.put("/user/notification-settings", json=payload, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["telegram_chat_id"] == "12345"


def test_notification_settings_requires_auth(api_client):
    r = api_client.get("/user/notification-settings")
    assert r.status_code == 401
