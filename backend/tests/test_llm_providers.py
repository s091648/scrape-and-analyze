import uuid
import os
import time
from jose import jwt
from unittest.mock import patch, MagicMock

os.environ["NEXTAUTH_SECRET"] = "test-secret"


def admin_token():
    return jwt.encode(
        {"sub": "admin", "role": "admin", "exp": int(time.time()) + 3600},
        "test-secret", algorithm="HS256",
    )


def _mock_provider(**kwargs):
    defaults = dict(
        id=uuid.uuid4(),
        name='gemini',
        model='gemini-test',
        api_key_env='GEMINI_API_KEY',
        priority=1,
        type='llm',
        is_active=True,
        rpm=5,
        tpm=250000,
        rpd=20,
        usage_24h=0,
        created_at=None,
        updated_at=None,
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=[])
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def test_list_providers_unauthenticated_returns_401():
    from backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    assert client.get("/llm-providers").status_code == 401


def test_list_providers_with_admin_returns_200():
    from backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    with patch("backend.routers.llm_providers.get_providers", return_value=[]):
        r = client.get("/llm-providers",
                       headers={"Authorization": f"Bearer {admin_token()}"})
    assert r.status_code == 200
    assert r.json() == []


def test_create_provider_with_admin_returns_201():
    from backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    payload = {
        "name": "gemini",
        "model": "gemini-2.5-flash",
        "api_key_env": "GEMINI_API_KEY",
        "priority": 1,
        "is_active": True,
        "rpm": 5,
        "tpm": 250000,
        "rpd": 20,
    }
    mock_p = _mock_provider(**payload)
    with patch("backend.routers.llm_providers.create_provider", return_value=mock_p):
        r = client.post("/llm-providers", json=payload,
                        headers={"Authorization": f"Bearer {admin_token()}"})
    assert r.status_code == 201


def test_create_provider_missing_required_field_returns_422():
    from backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    r = client.post("/llm-providers",
                    json={"name": "gemini"},
                    headers={"Authorization": f"Bearer {admin_token()}"})
    assert r.status_code == 422


def test_update_provider_with_admin_returns_200():
    from backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    pid = uuid.uuid4()
    mock_p = _mock_provider(id=pid)
    with patch("backend.routers.llm_providers.update_provider", return_value=mock_p):
        r = client.patch(f"/llm-providers/{pid}",
                         json={"priority": 2},
                         headers={"Authorization": f"Bearer {admin_token()}"})
    assert r.status_code == 200


def test_update_nonexistent_provider_returns_404():
    from backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    with patch("backend.routers.llm_providers.update_provider", return_value=None):
        r = client.patch(f"/llm-providers/{uuid.uuid4()}",
                         json={"priority": 2},
                         headers={"Authorization": f"Bearer {admin_token()}"})
    assert r.status_code == 404


def test_delete_provider_with_admin_returns_204():
    from backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    with patch("backend.routers.llm_providers.delete_provider", return_value=True):
        r = client.delete(f"/llm-providers/{uuid.uuid4()}",
                          headers={"Authorization": f"Bearer {admin_token()}"})
    assert r.status_code == 204


def test_delete_nonexistent_provider_returns_404():
    from backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    with patch("backend.routers.llm_providers.delete_provider", return_value=False):
        r = client.delete(f"/llm-providers/{uuid.uuid4()}",
                          headers={"Authorization": f"Bearer {admin_token()}"})
    assert r.status_code == 404