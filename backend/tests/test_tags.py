import uuid
import time
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from jose import jwt

SECRET = "test-secret"


def make_admin_token():
    payload = {"sub": "admin", "role": "admin", "exp": int(time.time()) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def make_mock_tag(name="Transformer", group="research"):
    tag = MagicMock()
    tag.id = uuid.uuid4()
    tag.name = name
    tag.tag_group_name = group
    return tag


def test_rename_tag_updates_name():
    from backend.main import app
    from backend.database import get_db
    client = TestClient(app)
    mock_tag = make_mock_tag()
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = mock_tag
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with patch("backend.routers.tags._tag_article_count", return_value=5):
            response = client.put(
                f"/tags/{mock_tag.id}",
                json={"name": "BERT"},
                headers={"Authorization": f"Bearer {make_admin_token()}"},
            )
        assert response.status_code == 200
        assert mock_tag.name == "BERT"
    finally:
        app.dependency_overrides.clear()


def test_move_tag_updates_group():
    from backend.main import app
    from backend.database import get_db
    client = TestClient(app)
    mock_tag = make_mock_tag()
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = mock_tag
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with patch("backend.routers.tags._tag_article_count", return_value=0):
            response = client.put(
                f"/tags/{mock_tag.id}",
                json={"tag_group_name": "applications"},
                headers={"Authorization": f"Bearer {make_admin_token()}"},
            )
        assert response.status_code == 200
        assert mock_tag.tag_group_name == "applications"
    finally:
        app.dependency_overrides.clear()


def test_batch_move_all_succeed():
    from backend.main import app
    from backend.database import get_db
    client = TestClient(app)
    tag1 = make_mock_tag("Tag1", "g1")
    tag2 = make_mock_tag("Tag2", "g1")
    tags_by_id = {str(tag1.id): tag1, str(tag2.id): tag2}

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.side_effect = lambda **kw: MagicMock(
        first=lambda: tags_by_id.get(str(kw.get("id")))
    )
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.post(
            "/tags/batch-move",
            json=[
                {"tag_id": str(tag1.id), "tag_group_name": "g2"},
                {"tag_id": str(tag2.id), "tag_group_name": "g2"},
            ],
            headers={"Authorization": f"Bearer {make_admin_token()}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["succeeded"]) == 2
        assert len(data["failed"]) == 0
    finally:
        app.dependency_overrides.clear()


def test_batch_move_missing_tag_goes_to_failed():
    from backend.main import app
    from backend.database import get_db
    client = TestClient(app)
    missing_id = str(uuid.uuid4())
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = None
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.post(
            "/tags/batch-move",
            json=[{"tag_id": missing_id, "tag_group_name": "g2"}],
            headers={"Authorization": f"Bearer {make_admin_token()}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["succeeded"]) == 0
        assert data["failed"][0]["tag_id"] == missing_id
    finally:
        app.dependency_overrides.clear()
