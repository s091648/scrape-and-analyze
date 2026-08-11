import os
import time
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from jose import jwt

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret")


def _admin_token():
    return jwt.encode(
        {"sub": "admin", "role": "admin", "exp": int(time.time()) + 3600},
        "test-secret",
        algorithm="HS256",
    )


def _guest_token():
    from backend.services.auth_service import create_guest_access_token
    return create_guest_access_token("test-guest-id")


def _mock_topic(**kwargs):
    t = MagicMock(spec=[])
    t.id = kwargs.get("id", uuid.uuid4())
    t.name = kwargs.get("name", "ai-ml")
    t.display_name = kwargs.get("display_name", "AI & ML")
    t.description = kwargs.get("description", None)
    t.color_hex = kwargs.get("color_hex", "#6366f1")
    t.prompt_override = kwargs.get("prompt_override", None)
    t.sort_order = kwargs.get("sort_order", 0)
    t.is_active = kwargs.get("is_active", True)
    t.tag_mode = kwargs.get("tag_mode", "unsupervised")
    t.created_at = None
    return t


def _override_db(mock_db):
    def override():
        yield mock_db

    return override


# ---------------------------------------------------------------------------
# GET /topics
# ---------------------------------------------------------------------------

def test_list_topics_returns_200():
    from backend.main import app
    from backend.database import get_db

    mock_topic = _mock_topic()
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [mock_topic]

    app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        client = TestClient(app)
        response = client.get("/topics", headers={"Authorization": f"Bearer {_guest_token()}"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "ai-ml"


def test_list_topics_include_inactive_skips_filter():
    from backend.main import app
    from backend.database import get_db

    mock_topic = _mock_topic(is_active=False)
    mock_db = MagicMock()
    # include_inactive=True → no filter_by, goes straight to order_by
    mock_db.query.return_value.order_by.return_value.all.return_value = [mock_topic]

    app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        client = TestClient(app)
        response = client.get("/topics?include_inactive=true", headers={"Authorization": f"Bearer {_guest_token()}"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()[0]["is_active"] is False


def test_list_topics_requires_at_least_a_guest_token():
    """018-public-api-auth: no longer fully public — a guest token (not a real login)
    is sufficient, but *some* valid token is now required."""
    from backend.main import app

    client = TestClient(app)
    response = client.get("/topics")
    assert response.status_code == 401


def test_list_topics_guest_token_is_sufficient():
    from backend.main import app
    from backend.database import get_db

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []

    app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        client = TestClient(app)
        response = client.get("/topics", headers={"Authorization": f"Bearer {_guest_token()}"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /topics
# ---------------------------------------------------------------------------

def test_create_topic_requires_admin():
    from backend.main import app

    client = TestClient(app)
    payload = {"name": "test", "display_name": "Test"}
    response = client.post("/topics", json=payload)
    assert response.status_code == 401


def test_create_topic_with_admin_returns_201():
    from backend.main import app
    from backend.database import get_db

    mock_topic = _mock_topic()
    mock_db = MagicMock()

    MockTopic = MagicMock(return_value=mock_topic)

    app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        client = TestClient(app)
        payload = {"name": "ai-ml", "display_name": "AI & ML"}
        with patch("models.topic.Topic", MockTopic):
            response = client.post(
                "/topics",
                json=payload,
                headers={"Authorization": f"Bearer {_admin_token()}"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 201
    assert response.json()["name"] == "ai-ml"


# ---------------------------------------------------------------------------
# PATCH /topics/{id}
# ---------------------------------------------------------------------------

def test_update_topic_requires_admin():
    from backend.main import app

    topic_id = uuid.uuid4()
    client = TestClient(app)
    response = client.patch(f"/topics/{topic_id}", json={"display_name": "Updated"})
    assert response.status_code == 401


def test_update_topic_not_found_returns_404():
    from backend.main import app
    from backend.database import get_db

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = None

    app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        client = TestClient(app)
        response = client.patch(
            f"/topics/{uuid.uuid4()}",
            json={"display_name": "Updated"},
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404


def test_update_topic_with_admin_returns_200():
    from backend.main import app
    from backend.database import get_db

    mock_topic = _mock_topic(display_name="Updated")
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = mock_topic

    app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        client = TestClient(app)
        response = client.patch(
            f"/topics/{uuid.uuid4()}",
            json={"display_name": "Updated"},
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated"


# ---------------------------------------------------------------------------
# DELETE /topics/{id}
# ---------------------------------------------------------------------------

def test_delete_topic_requires_admin():
    from backend.main import app

    client = TestClient(app)
    response = client.delete(f"/topics/{uuid.uuid4()}")
    assert response.status_code == 401


def test_delete_topic_not_found_returns_404():
    from backend.main import app
    from backend.database import get_db

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = None

    app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        client = TestClient(app)
        response = client.delete(
            f"/topics/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /topics — caching (020-redis-caching-layer)
# ---------------------------------------------------------------------------

def test_list_topics_sets_x_cache_header():
    from backend.main import app
    from backend.database import get_db

    mock_topic = _mock_topic()
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [mock_topic]

    app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        client = TestClient(app)
        response = client.get("/topics", headers={"Authorization": f"Bearer {_guest_token()}"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert "X-Cache" in response.headers


class _InMemoryFakeCacheGateway:
    """Minimal in-memory CacheGateway stand-in — mirrors test_graph.py's version. Real
    cache-aside behavior is covered by backend/tests/integration/test_topics.py; this
    only confirms list_topics() actually calls through CacheGateway.get_or_set()."""

    def __init__(self):
        self._store = {}

    def get_or_set(self, namespace, params, ttl_seconds, loader, lang="en"):
        import json
        from shared.cache import CacheResult
        key = (namespace, lang, json.dumps(params, sort_keys=True, default=str))
        if key not in self._store:
            self._store[key] = loader()
            return CacheResult(value=self._store[key], status="MISS")
        return CacheResult(value=self._store[key], status="HIT")

    def bump_version(self, namespace):
        return 0


def test_list_topics_cache_hit_avoids_second_query():
    from backend.main import app
    from backend.database import get_db
    from backend.cache import get_cache_gateway

    mock_topic = _mock_topic()
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [mock_topic]
    fake_gateway = _InMemoryFakeCacheGateway()

    app.dependency_overrides[get_db] = _override_db(mock_db)
    app.dependency_overrides[get_cache_gateway] = lambda: fake_gateway
    try:
        client = TestClient(app)
        first = client.get("/topics", headers={"Authorization": f"Bearer {_guest_token()}"})
        second = client.get("/topics", headers={"Authorization": f"Bearer {_guest_token()}"})
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_cache_gateway, None)

    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert mock_db.query.return_value.filter_by.return_value.order_by.return_value.all.call_count == 1


def test_delete_topic_soft_deletes_returns_204():
    from backend.main import app
    from backend.database import get_db

    mock_topic = _mock_topic()
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = mock_topic

    app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        client = TestClient(app)
        response = client.delete(
            f"/topics/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 204
    assert mock_topic.is_active is False
