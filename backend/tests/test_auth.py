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
    """Email exists and google_id already set — sign in succeeds."""
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
    mock_user.google_id = "sub-abc"   # already linked
    mock_user.created_at = None
    mock_user.updated_at = None
    with patch("backend.routers.auth._get_user_by_email", return_value=mock_user):
        response = client.post("/auth/google/authorize", json={
            "email": "known@test.com", "google_id": "sub-abc", "name": "Known"
        })
    assert response.status_code == 200
    assert response.json()["role"] == "user"


def test_google_authorize_unlinked_email_returns_409():
    """Email exists but has no google_id — must not auto-link, return 409."""
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.email = "creds@test.com"
    mock_user.name = "Creds User"
    mock_user.username = "credsuser"
    mock_user.role = "user"
    mock_user.is_allowed = True
    mock_user.google_id = None      # <-- no google_id linked yet
    mock_user.created_at = None
    mock_user.updated_at = None
    with patch("backend.routers.auth._get_user_by_email", return_value=mock_user):
        response = client.post("/auth/google/authorize", json={
            "email": "creds@test.com", "google_id": "new-sub-456", "name": "Creds User"
        })
    assert response.status_code == 409


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


def _make_creds(token):
    from fastapi.security import HTTPAuthorizationCredentials
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_require_user_valid_token():
    from backend.auth import guards
    from fastapi.security import HTTPAuthorizationCredentials
    token = make_token(role="user")
    creds = _make_creds(token)
    payload = guards.require_user.impl(creds)
    assert payload["role"] == "user"


def test_require_user_accepts_admin():
    from backend.auth import guards
    from fastapi.security import HTTPAuthorizationCredentials
    token = make_token(role="admin")
    creds = _make_creds(token)
    payload = guards.require_user.impl(creds)
    assert payload["role"] == "admin"


def test_require_user_rejects_expired():
    from backend.auth import guards
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    token = make_token(role="user", exp_offset=-1)
    creds = _make_creds(token)
    with pytest.raises(HTTPException) as exc:
        guards.require_user.impl(creds)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# /auth/me endpoint tests
# ---------------------------------------------------------------------------

def make_user_token(user_id: str, role: str = "user"):
    """Make a JWT with a real UUID sub claim."""
    payload = {"sub": user_id, "role": role, "exp": int(time.time()) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def _make_mock_profile_user(user_id=None):
    """Return a MagicMock resembling a User ORM object with profile fields."""
    from unittest.mock import MagicMock
    mock_user = MagicMock()
    mock_user.id = user_id or uuid.uuid4()
    mock_user.email = "profile@test.com"
    mock_user.name = "Profile User"
    mock_user.username = "profileuser"
    mock_user.role = "user"
    mock_user.icon = None
    mock_user.google_id = None
    mock_user.created_at = None
    mock_user.hashed_password = bcrypt.hashpw(b"correctpass", bcrypt.gensalt()).decode()
    return mock_user


def _make_mock_google_user(user_id=None):
    """Return a MagicMock resembling a Google-only User (no hashed_password)."""
    from unittest.mock import MagicMock
    mock_user = MagicMock()
    mock_user.id = user_id or uuid.uuid4()
    mock_user.email = "googleonly@test.com"
    mock_user.name = "Google Only"
    mock_user.username = None
    mock_user.role = "user"
    mock_user.icon = None
    mock_user.google_id = "google-sub-999"
    mock_user.created_at = None
    mock_user.hashed_password = None
    return mock_user


# GET /auth/me

def test_get_me_returns_profile():
    from backend.main import app
    from unittest.mock import patch
    client = TestClient(app)
    uid = uuid.uuid4()
    mock_user = _make_mock_profile_user(user_id=uid)
    token = make_user_token(str(uid))
    with patch("backend.routers.auth._get_user_by_id", return_value=mock_user):
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "profile@test.com"
    assert data["username"] == "profileuser"
    assert data["role"] == "user"


def test_get_me_no_token():
    from backend.main import app
    client = TestClient(app)
    response = client.get("/auth/me")
    # HTTPBearer returns 403 when no credentials are provided (auto_error=True default)
    # In some FastAPI versions this may be 401 or 403 — accept either
    assert response.status_code in (401, 403)


# PATCH /auth/me

def test_update_me_name():
    from backend.main import app
    from backend.database import get_db
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    uid = uuid.uuid4()
    mock_user = _make_mock_profile_user(user_id=uid)
    token = make_user_token(str(uid))

    mock_db = MagicMock()

    def fake_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = fake_get_db
    try:
        with patch("backend.routers.auth._get_user_by_id", return_value=mock_user):
            response = client.patch(
                "/auth/me",
                headers={"Authorization": f"Bearer {token}"},
                json={"name": "Updated Name"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert "role" in response.json()


def test_update_me_icon():
    from backend.main import app
    from backend.database import get_db
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    uid = uuid.uuid4()
    mock_user = _make_mock_profile_user(user_id=uid)
    token = make_user_token(str(uid))

    mock_db = MagicMock()

    def fake_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = fake_get_db
    try:
        with patch("backend.routers.auth._get_user_by_id", return_value=mock_user):
            response = client.patch(
                "/auth/me",
                headers={"Authorization": f"Bearer {token}"},
                json={"icon": "https://example.com/avatar.png"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert "role" in response.json()


# POST /auth/me/password

def test_change_password_success():
    from backend.main import app
    from unittest.mock import patch
    client = TestClient(app)
    uid = uuid.uuid4()
    mock_user = _make_mock_profile_user(user_id=uid)
    token = make_user_token(str(uid))
    with patch("backend.routers.auth._get_user_by_id", return_value=mock_user):
        response = client.post(
            "/auth/me/password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "correctpass", "new_password": "newpass123"},
        )
    assert response.status_code == 204


def test_change_password_wrong_current():
    from backend.main import app
    from unittest.mock import patch
    client = TestClient(app)
    uid = uuid.uuid4()
    mock_user = _make_mock_profile_user(user_id=uid)
    token = make_user_token(str(uid))
    with patch("backend.routers.auth._get_user_by_id", return_value=mock_user):
        response = client.post(
            "/auth/me/password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "wrongpass", "new_password": "newpass123"},
        )
    assert response.status_code == 400


def test_change_password_google_only():
    from backend.main import app
    from unittest.mock import patch
    client = TestClient(app)
    uid = uuid.uuid4()
    mock_user = _make_mock_google_user(user_id=uid)
    token = make_user_token(str(uid))
    with patch("backend.routers.auth._get_user_by_id", return_value=mock_user):
        response = client.post(
            "/auth/me/password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "anything", "new_password": "newpass123"},
        )
    assert response.status_code == 400


# DELETE /auth/me

def test_delete_me():
    from backend.main import app
    from unittest.mock import patch
    client = TestClient(app)
    uid = uuid.uuid4()
    mock_user = _make_mock_profile_user(user_id=uid)
    token = make_user_token(str(uid))
    with patch("backend.routers.auth._get_user_by_id", return_value=mock_user), \
         patch("backend.routers.auth._delete_user"):
        response = client.delete(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# /auth/me/link-google endpoint tests
# ---------------------------------------------------------------------------

def test_link_google_success():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    user_id = uuid.uuid4()
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.google_id = None
    mock_user.username = "alice"
    mock_user.name = "Alice"
    mock_user.email = "alice@test.com"
    mock_user.role = "user"
    mock_user.is_allowed = True
    mock_user.icon = None
    mock_user.created_at = None
    token = make_user_token(str(user_id), role="user")
    with patch("backend.routers.auth._get_user_by_id", return_value=mock_user), \
         patch("backend.routers.auth._get_user_by_google_id", return_value=None), \
         patch("backend.routers.auth._update_google_id"):
        response = client.post(
            "/auth/me/link-google",
            json={"google_id": "new-google-sub"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 204


def test_link_google_already_linked_returns_400():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    user_id = uuid.uuid4()
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.google_id = "existing-sub"
    token = make_user_token(str(user_id), role="user")
    with patch("backend.routers.auth._get_user_by_id", return_value=mock_user):
        response = client.post(
            "/auth/me/link-google",
            json={"google_id": "new-sub"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 400


def test_link_google_id_taken_returns_409():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    user_id = uuid.uuid4()
    current_user = MagicMock()
    current_user.id = user_id
    current_user.google_id = None
    other_user = MagicMock()
    other_user.id = uuid.uuid4()
    token = make_user_token(str(user_id), role="user")
    with patch("backend.routers.auth._get_user_by_id", return_value=current_user), \
         patch("backend.routers.auth._get_user_by_google_id", return_value=other_user):
        response = client.post(
            "/auth/me/link-google",
            json={"google_id": "taken-sub"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 409


def test_unlink_google_success():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    user_id = uuid.uuid4()
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.google_id = "some-sub"
    mock_user.username = "alice"  # has username — safe to unlink
    token = make_user_token(str(user_id), role="user")
    with patch("backend.routers.auth._get_user_by_id", return_value=mock_user):
        response = client.delete(
            "/auth/me/link-google",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 204


def test_unlink_google_no_username_returns_400():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    user_id = uuid.uuid4()
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.google_id = "some-sub"
    mock_user.username = None  # Google-only account — would be locked out
    token = make_user_token(str(user_id), role="user")
    with patch("backend.routers.auth._get_user_by_id", return_value=mock_user):
        response = client.delete(
            "/auth/me/link-google",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 400
