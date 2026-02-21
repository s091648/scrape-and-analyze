import os
import pytest
import time
from jose import jwt

SECRET = "test-secret-key"
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
    result = require_admin.__wrapped__(token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert result["role"] == "admin"


def test_expired_token_returns_401():
    from backend.auth.guards import require_admin
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    token = make_token(exp_offset=-10)  # already expired
    with pytest.raises(HTTPException) as exc:
        require_admin.__wrapped__(token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert exc.value.status_code == 401


def test_missing_exp_claim_returns_401():
    from backend.auth.guards import require_admin
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    token = make_token(include_exp=False)
    with pytest.raises(HTTPException) as exc:
        require_admin.__wrapped__(token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert exc.value.status_code == 401


def test_viewer_role_returns_403():
    from backend.auth.guards import require_admin
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    token = make_token(role="viewer")
    with pytest.raises(HTTPException) as exc:
        require_admin.__wrapped__(token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert exc.value.status_code == 403
