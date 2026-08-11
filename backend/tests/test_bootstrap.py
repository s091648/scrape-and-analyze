import os
import time
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from jose import jwt

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret")


def _mock_topic(**kwargs):
    import uuid
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


def test_bootstrap_returns_200_with_token_topics_and_languages():
    from backend.main import app
    from backend.database import get_db

    mock_topic = _mock_topic()
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [mock_topic]

    app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        client = TestClient(app)
        response = client.post("/bootstrap")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"access_token", "expires_in", "topics", "languages"}
    assert data["expires_in"] == 3600
    assert len(data["topics"]) == 1
    assert data["topics"][0]["name"] == "ai-ml"
    codes = [lang["code"] for lang in data["languages"]["available"]]
    assert "en" in codes
    assert "zh-TW" in codes


def test_bootstrap_requires_no_authorization_header():
    from backend.main import app
    from backend.database import get_db

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []

    app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        client = TestClient(app)
        # No Authorization header at all — must still succeed (this is the bootstrap endpoint).
        response = client.post("/bootstrap")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


def test_bootstrap_mints_a_usable_guest_access_token():
    from backend.main import app
    from backend.database import get_db

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []

    app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        client = TestClient(app)
        response = client.post("/bootstrap")
    finally:
        app.dependency_overrides.pop(get_db, None)

    token = response.json()["access_token"]
    payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
    assert payload["tier"] == "guest"
    assert payload["token_use"] == "access"
    assert payload["exp"] > int(time.time())


def test_bootstrap_excludes_inactive_topics():
    from backend.main import app
    from backend.database import get_db

    mock_topic = _mock_topic(is_active=True)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [mock_topic]

    app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        client = TestClient(app)
        response = client.post("/bootstrap")
    finally:
        app.dependency_overrides.pop(get_db, None)

    # filter_by(is_active=True) must have been the call actually used to build the query
    mock_db.query.return_value.filter_by.assert_called_with(is_active=True)
    assert response.json()["topics"][0]["is_active"] is True


def test_bootstrap_no_ip_resolves_en():
    from backend.main import app
    from backend.database import get_db

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []

    app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        client = TestClient(app)
        with patch("backend.routers.bootstrap.resolve_language_from_ip", return_value="en"):
            response = client.post("/bootstrap")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.json()["languages"]["resolved"] == "en"


def test_bootstrap_forwarded_for_header_is_used():
    from backend.main import app
    from backend.database import get_db

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []

    app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        client = TestClient(app)
        with patch("backend.routers.bootstrap.resolve_language_from_ip", return_value="zh-TW") as mock_resolve:
            response = client.post("/bootstrap", headers={"X-Forwarded-For": "1.2.3.4, 10.0.0.1"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["languages"]["resolved"] == "zh-TW"
    mock_resolve.assert_called_once_with("1.2.3.4")


class _InMemoryFakeCacheGateway:
    """Mirrors test_topics.py's version — confirms /bootstrap shares the "topics"
    cache namespace with GET /topics rather than maintaining its own separate cache."""

    def __init__(self):
        self._store = {}
        self.calls = []

    def get_or_set(self, namespace, params, ttl_seconds, loader, lang="en"):
        import json
        from shared.cache import CacheResult
        self.calls.append((namespace, params))
        key = (namespace, lang, json.dumps(params, sort_keys=True, default=str))
        if key not in self._store:
            self._store[key] = loader()
            return CacheResult(value=self._store[key], status="MISS")
        return CacheResult(value=self._store[key], status="HIT")

    def bump_version(self, namespace):
        return 0


def test_bootstrap_topics_cache_is_shared_with_get_topics():
    from backend.main import app
    from backend.database import get_db
    from backend.cache import get_cache_gateway

    mock_topic = _mock_topic()
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [mock_topic]
    fake_gateway = _InMemoryFakeCacheGateway()

    def _guest_token():
        from backend.services.auth_service import create_guest_access_token
        return create_guest_access_token("test-guest-id")

    app.dependency_overrides[get_db] = _override_db(mock_db)
    app.dependency_overrides[get_cache_gateway] = lambda: fake_gateway
    try:
        client = TestClient(app)
        bootstrap_response = client.post("/bootstrap")
        topics_response = client.get("/topics", headers={"Authorization": f"Bearer {_guest_token()}"})
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_cache_gateway, None)

    assert bootstrap_response.status_code == 200
    assert topics_response.headers["X-Cache"] == "HIT"
    assert mock_db.query.return_value.filter_by.return_value.order_by.return_value.all.call_count == 1
