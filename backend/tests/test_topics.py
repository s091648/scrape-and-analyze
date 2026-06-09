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
        response = client.get("/topics")
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
        response = client.get("/topics?include_inactive=true")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()[0]["is_active"] is False


def test_list_topics_no_auth_required():
    from backend.main import app
    from backend.database import get_db

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []

    app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        client = TestClient(app)
        response = client.get("/topics")
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
