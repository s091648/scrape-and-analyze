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


def _mock_setting(source_type: str, selector_config=None):
    setting = MagicMock(spec=[])
    setting.id = uuid.uuid4()
    setting.source_type = source_type
    setting.name = source_type.replace("_", " ").title()
    setting.url = ""
    setting.frequency = 24
    setting.is_active = True
    setting.topic_id = uuid.uuid4()
    setting.selector_config = selector_config
    setting.last_scraped_at = None
    setting.created_at = None
    setting.updated_at = None
    return setting


def test_post_setting_semantic_scholar_returns_201():
    from backend.main import app
    client = TestClient(app)
    payload = {
        "source_type": "semantic_scholar",
        "name": "Semantic Scholar",
        "url": "",
        "frequency": 24,
        "is_active": True,
        "topic_id": str(uuid.uuid4()),
        "selector_config": {"type": "semantic_scholar", "max_results": 20, "days_back": 7},
    }
    with patch("backend.routers.scraper_settings.create_setting",
               return_value=_mock_setting("semantic_scholar", payload["selector_config"])):
        response = client.post(
            "/scraper-settings",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token()}"}
        )
    assert response.status_code == 201
    assert response.json()["source_type"] == "semantic_scholar"


def test_post_setting_openalex_returns_201():
    from backend.main import app
    client = TestClient(app)
    payload = {
        "source_type": "openalex",
        "name": "OpenAlex",
        "url": "",
        "frequency": 24,
        "is_active": True,
        "topic_id": str(uuid.uuid4()),
        "selector_config": {"type": "openalex", "max_results": 20, "days_back": 7},
    }
    with patch("backend.routers.scraper_settings.create_setting",
               return_value=_mock_setting("openalex", payload["selector_config"])):
        response = client.post(
            "/scraper-settings",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token()}"}
        )
    assert response.status_code == 201
    assert response.json()["source_type"] == "openalex"


def test_post_setting_arxiv_returns_201():
    from backend.main import app
    client = TestClient(app)
    payload = {
        "source_type": "arxiv",
        "name": "ArXiv",
        "url": "",
        "frequency": 24,
        "is_active": True,
        "topic_id": str(uuid.uuid4()),
        "selector_config": {"type": "arxiv", "max_results": 30, "days_back": 7},
    }
    with patch("backend.routers.scraper_settings.create_setting",
               return_value=_mock_setting("arxiv", payload["selector_config"])):
        response = client.post(
            "/scraper-settings",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token()}"}
        )
    assert response.status_code == 201


def test_post_setting_unknown_source_type_returns_422():
    from backend.main import app
    client = TestClient(app)
    payload = {
        "source_type": "totally_unknown",
        "name": "test",
        "url": "",
        "frequency": 24,
        "is_active": True,
        "topic_id": str(uuid.uuid4()),
    }
    response = client.post(
        "/scraper-settings",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token()}"}
    )
    assert response.status_code == 422
