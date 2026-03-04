import os
import uuid
import pytest
import time
import bcrypt
from jose import jwt
from starlette.testclient import TestClient

SECRET = "test-secret"  # matches conftest.py NEXTAUTH_SECRET
os.environ["NEXTAUTH_SECRET"] = SECRET


def make_token(role="admin", exp_offset=3600, include_exp=True):
    payload = {"sub": "admin", "role": role}
    if include_exp:
        payload["exp"] = int(time.time()) + exp_offset
    return jwt.encode(payload, SECRET, algorithm="HS256")


def test_valid_admin_token_passes():
    from backend.auth.guards import require_admin
    from fastapi.security import HTTPAuthorizationCredentials
    token = make_token(role="admin")
    result = require_admin.impl(token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert result["role"] == "admin"


def test_expired_token_returns_401():
    from backend.auth.guards import require_admin
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    token = make_token(exp_offset=-10)  # already expired
    with pytest.raises(HTTPException) as exc:
        require_admin.impl(token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert exc.value.status_code == 401


def test_missing_exp_claim_returns_401():
    from backend.auth.guards import require_admin
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    token = make_token(include_exp=False)
    with pytest.raises(HTTPException) as exc:
        require_admin.impl(token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert exc.value.status_code == 401


def test_viewer_role_returns_403():
    from backend.auth.guards import require_admin
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    token = make_token(role="viewer")
    with pytest.raises(HTTPException) as exc:
        require_admin.impl(token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert exc.value.status_code == 403


def test_verify_disabled_user_returns_403():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.username = 'disabled'
    mock_user.role = 'user'
    mock_user.is_allowed = False
    mock_user.hashed_password = bcrypt.hashpw(b'pass', bcrypt.gensalt()).decode()
    with patch("backend.routers.auth._get_user_by_username", return_value=mock_user):
        response = client.post("/auth/verify", json={"username": "disabled", "password": "pass"})
    assert response.status_code == 403


def admin_token():
    return make_token(role="admin")


def test_register_credentials_returns_201():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    created = MagicMock()
    created.id = uuid.uuid4()
    created.email = "new@test.com"
    created.name = "New User"
    created.username = "newuser"
    created.role = "user"
    created.is_allowed = True
    created.google_id = None
    created.created_at = None
    created.updated_at = None
    with patch("backend.routers.auth._create_user", return_value=created):
        response = client.post("/auth/register", json={
            "username": "newuser", "password": "pass123",
            "email": "new@test.com", "name": "New User"
        })
    assert response.status_code == 201
    assert response.json()["role"] == "user"


def test_register_google_returns_201():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    created = MagicMock()
    created.id = uuid.uuid4()
    created.email = "google@test.com"
    created.name = "Google User"
    created.username = None
    created.role = "user"
    created.is_allowed = True
    created.google_id = "google-sub-123"
    created.created_at = None
    created.updated_at = None
    with patch("backend.routers.auth._create_user", return_value=created):
        response = client.post("/auth/register", json={
            "email": "google@test.com", "name": "Google User", "google_id": "google-sub-123"
        })
    assert response.status_code == 201


def test_register_duplicate_email_returns_409():
    from backend.main import app
    from unittest.mock import patch
    client = TestClient(app)
    with patch("backend.routers.auth._create_user",
               side_effect=Exception("duplicate key value violates unique constraint")):
        response = client.post("/auth/register", json={
            "username": "dup", "password": "pass", "email": "dup@test.com"
        })
    assert response.status_code == 409


def test_google_authorize_known_user_returns_200():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.email = "known@test.com"
    mock_user.name = "Known"
    mock_user.username = None
    mock_user.role = "user"
    mock_user.is_allowed = True
    mock_user.google_id = None
    mock_user.created_at = None
    mock_user.updated_at = None
    with patch("backend.routers.auth._get_user_by_email", return_value=mock_user), \
         patch("backend.routers.auth._update_google_id"):
        response = client.post("/auth/google/authorize", json={
            "email": "known@test.com", "google_id": "sub-abc", "name": "Known"
        })
    assert response.status_code == 200
    assert response.json()["role"] == "user"


def test_google_authorize_unknown_user_returns_404():
    from backend.main import app
    from unittest.mock import patch
    client = TestClient(app)
    with patch("backend.routers.auth._get_user_by_email", return_value=None):
        response = client.post("/auth/google/authorize", json={
            "email": "unknown@test.com", "google_id": "sub-xyz", "name": "X"
        })
    assert response.status_code == 404


def test_google_authorize_disabled_user_returns_403():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    mock_user = MagicMock()
    mock_user.is_allowed = False
    with patch("backend.routers.auth._get_user_by_email", return_value=mock_user):
        response = client.post("/auth/google/authorize", json={
            "email": "banned@test.com", "google_id": "sub-ban", "name": "Banned"
        })
    assert response.status_code == 403


def test_list_users_as_admin_returns_200():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.email = "u@test.com"
    mock_user.name = "U"
    mock_user.username = "u"
    mock_user.role = "user"
    mock_user.is_allowed = True
    mock_user.google_id = None
    mock_user.created_at = None
    mock_user.updated_at = None
    with patch("backend.routers.auth._list_users", return_value=[mock_user]):
        response = client.get("/auth/users",
                              headers={"Authorization": f"Bearer {admin_token()}"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_users_without_admin_returns_401():
    from backend.main import app
    client = TestClient(app)
    response = client.get("/auth/users")
    assert response.status_code == 401


def test_update_user_role_as_admin_returns_200():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    uid = uuid.uuid4()
    mock_user = MagicMock()
    mock_user.id = uid
    mock_user.email = "u@test.com"
    mock_user.name = "U"
    mock_user.username = "u"
    mock_user.role = "admin"
    mock_user.is_allowed = True
    mock_user.google_id = None
    mock_user.created_at = None
    mock_user.updated_at = None
    with patch("backend.routers.auth._get_user_by_id", return_value=mock_user), \
         patch("backend.routers.auth._update_user", return_value=mock_user):
        response = client.patch(f"/auth/users/{uid}",
                                headers={"Authorization": f"Bearer {admin_token()}"},
                                json={"role": "admin"})
    assert response.status_code == 200


def test_delete_user_as_admin_returns_204():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    uid = uuid.uuid4()
    mock_user = MagicMock()
    with patch("backend.routers.auth._get_user_by_id", return_value=mock_user), \
         patch("backend.routers.auth._delete_user"):
        response = client.delete(f"/auth/users/{uid}",
                                 headers={"Authorization": f"Bearer {admin_token()}"})
    assert response.status_code == 204
