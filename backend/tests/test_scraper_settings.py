import uuid
import os
import time
from jose import jwt
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

os.environ["NEXTAUTH_SECRET"] = "test-secret"


def admin_token():
    return jwt.encode(
        {"sub": "admin", "role": "admin", "exp": int(time.time()) + 3600},
        "test-secret", algorithm="HS256"
    )


def test_get_settings_unauthenticated_returns_401():
    from backend.main import app
    client = TestClient(app)
    response = client.get("/scraper-settings")
    assert response.status_code == 401


def test_post_setting_with_admin_token_returns_201():
    from backend.main import app
    client = TestClient(app)
    payload = {"source_type": "rss", "name": "test", "url": "https://test.com/feed",
               "frequency": 24, "is_active": True, "topic_id": str(uuid.uuid4())}
    mock_setting = MagicMock(spec=[])  # spec=[] prevents attribute magic interception
    mock_setting.id = uuid.uuid4()
    mock_setting.source_type = payload["source_type"]
    mock_setting.name = payload["name"]
    mock_setting.url = payload["url"]
    mock_setting.frequency = payload["frequency"]
    mock_setting.is_active = payload["is_active"]
    mock_setting.topic_id = payload["topic_id"]
    mock_setting.selector_config = None
    mock_setting.created_at = None
    mock_setting.updated_at = None
    with patch("backend.routers.scraper_settings.create_setting", return_value=mock_setting):
        response = client.post(
            "/scraper-settings",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token()}"}
        )
    assert response.status_code == 201


def test_post_setting_invalid_source_type_returns_422():
    from backend.main import app
    client = TestClient(app)
    payload = {"source_type": "unknown_type", "name": "test", "url": "https://test.com",
               "frequency": "daily", "is_active": True}
    response = client.post(
        "/scraper-settings",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token()}"}
    )
    assert response.status_code == 422


def test_delete_setting_with_admin_returns_204():
    from backend.main import app
    client = TestClient(app)
    setting_id = uuid.uuid4()
    with patch("backend.routers.scraper_settings.delete_setting", return_value=True):
        response = client.delete(
            f"/scraper-settings/{setting_id}",
            headers={"Authorization": f"Bearer {admin_token()}"}
        )
    assert response.status_code == 204
