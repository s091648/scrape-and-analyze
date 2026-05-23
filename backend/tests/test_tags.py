import uuid
import time
from types import SimpleNamespace
from unittest.mock import MagicMock
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
    mock_db.query.return_value.filter.return_value.scalar.return_value = 5
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
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
    mock_db.query.return_value.filter.return_value.scalar.return_value = 0
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
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

def test_list_tag_groups_with_topic_id_excludes_zero_count_tags():
    """When topic_id is given, only tags that have articles in that topic appear."""
    from backend.main import app
    from backend.database import get_db
    client = TestClient(app)

    topic_id = uuid.uuid4()
    grp_id = uuid.uuid4()

    mock_group = MagicMock()
    mock_group.id = grp_id
    mock_group.name = "research_methods"
    mock_group.display_name = "Research Methods"
    mock_group.description = None
    mock_group.color_hex = None
    mock_group.topic_id = topic_id
    mock_group.embedding = None

    mock_db = MagicMock()
    # Group query chain: query().filter().order_by().all()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_group]
    # Tag ORM query chain: query().join().join().filter().group_by().order_by().all()
    mock_db.query.return_value.join.return_value.join.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = []

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.get(f"/tag-groups?topic_id={topic_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["tags"] == []
    finally:
        app.dependency_overrides.clear()


def test_list_tag_groups_with_topic_id_returns_tags_with_counts():
    """Tags present in the topic appear with their article count."""
    from backend.main import app
    from backend.database import get_db
    client = TestClient(app)

    topic_id = uuid.uuid4()
    grp_id = uuid.uuid4()
    tag_id = uuid.uuid4()

    mock_group = MagicMock()
    mock_group.id = grp_id
    mock_group.name = "research_methods"
    mock_group.display_name = "Research Methods"
    mock_group.description = None
    mock_group.color_hex = None
    mock_group.topic_id = topic_id
    mock_group.embedding = None

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_group]
    # Tag ORM query chain returns one row with attribute access
    mock_tag_row = SimpleNamespace(id=tag_id, name="Transformer", article_count=3)
    mock_db.query.return_value.join.return_value.join.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = [mock_tag_row]

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.get(f"/tag-groups?topic_id={topic_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data[0]["tags"]) == 1
        assert data[0]["tags"][0]["name"] == "Transformer"
        assert data[0]["tags"][0]["article_count"] == 3
    finally:
        app.dependency_overrides.clear()

def test_create_tag_group_succeeds_even_without_gemini_key(monkeypatch):
    """Tag group creation works even if GEMINI_API_KEY is absent."""
    import os
    from backend.main import app
    from backend.database import get_db
    client = TestClient(app)

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    grp_id = uuid.uuid4()
    topic_id = uuid.uuid4()

    mock_grp = MagicMock()
    mock_grp.id = grp_id
    mock_grp.name = "test_group"
    mock_grp.display_name = "Test Group"
    mock_grp.description = None
    mock_grp.color_hex = None
    mock_grp.topic_id = topic_id

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = mock_grp

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.post(
            "/tag-groups",
            json={"name": "test_group", "display_name": "Test Group", "topic_id": str(topic_id)},
            headers={"Authorization": f"Bearer {make_admin_token()}"},
        )
        assert response.status_code == 201
    finally:
        app.dependency_overrides.clear()