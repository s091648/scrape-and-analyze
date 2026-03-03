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
