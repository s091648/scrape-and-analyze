"""Unit tests for backend.auth.guards._require_admin_impl / _require_user_impl raising
the shared DomainError authorization categories instead of HTTPException directly."""
import os
import time
import uuid

import pytest
from jose import jwt
from fastapi.security import HTTPAuthorizationCredentials

from shared.domain.exceptions import UnauthorizedError, ForbiddenError

SECRET = "test-secret"  # matches conftest.py NEXTAUTH_SECRET
os.environ["NEXTAUTH_SECRET"] = SECRET


def make_token(role=None, exp_offset=3600, include_exp=True):
    payload = {"sub": "user-id"}
    if role is not None:
        payload["role"] = role
    if include_exp:
        payload["exp"] = int(time.time()) + exp_offset
    return jwt.encode(payload, SECRET, algorithm="HS256")


def _creds(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_require_admin_raises_unauthorized_on_invalid_token():
    from backend.auth.guards import require_admin
    with pytest.raises(UnauthorizedError):
        require_admin.impl(_creds("not-a-jwt"))


def test_require_admin_raises_unauthorized_on_missing_exp():
    from backend.auth.guards import require_admin
    with pytest.raises(UnauthorizedError):
        require_admin.impl(_creds(make_token(role="admin", include_exp=False)))


def test_require_admin_raises_unauthorized_on_expired_token():
    from backend.auth.guards import require_admin
    with pytest.raises(UnauthorizedError):
        require_admin.impl(_creds(make_token(role="admin", exp_offset=-10)))


def test_require_admin_raises_forbidden_for_non_admin_role():
    from backend.auth.guards import require_admin
    with pytest.raises(ForbiddenError):
        require_admin.impl(_creds(make_token(role="user")))


def test_require_admin_succeeds_for_admin_role():
    from backend.auth.guards import require_admin
    payload = require_admin.impl(_creds(make_token(role="admin")))
    assert payload["role"] == "admin"


def test_require_user_raises_unauthorized_on_invalid_token():
    from backend.auth.guards import require_user
    with pytest.raises(UnauthorizedError):
        require_user.impl(_creds("not-a-jwt"))


def test_require_user_raises_unauthorized_on_expired_token():
    from backend.auth.guards import require_user
    with pytest.raises(UnauthorizedError):
        require_user.impl(_creds(make_token(exp_offset=-10)))


def test_require_user_succeeds_for_valid_token():
    from backend.auth.guards import require_user
    payload = require_user.impl(_creds(make_token()))
    assert payload["sub"] == "user-id"


def test_require_user_rejects_guest_token():
    """018-public-api-auth: a guest token is valid and non-expired, but is not
    "a specific logged-in user" — require_user must still refuse it."""
    from backend.auth.guards import require_user
    guest_payload = {"tier": "guest", "guest_id": "abc", "token_use": "access",
                      "exp": int(time.time()) + 3600}
    token = jwt.encode(guest_payload, SECRET, algorithm="HS256")
    with pytest.raises(UnauthorizedError):
        require_user.impl(_creds(token))


def make_guest_token(token_use="access", exp_offset=3600, guest_id="abc123"):
    payload = {"tier": "guest", "guest_id": guest_id, "token_use": token_use}
    if exp_offset is not None:
        payload["exp"] = int(time.time()) + exp_offset
    return jwt.encode(payload, SECRET, algorithm="HS256")


def test_require_any_token_accepts_real_user_token():
    from backend.auth.guards import require_any_token
    payload = require_any_token.impl(_creds(make_token(role="user")))
    assert payload["role"] == "user"


def test_require_any_token_accepts_real_admin_token():
    from backend.auth.guards import require_any_token
    payload = require_any_token.impl(_creds(make_token(role="admin")))
    assert payload["role"] == "admin"


def test_require_any_token_accepts_guest_access_token():
    from backend.auth.guards import require_any_token
    payload = require_any_token.impl(_creds(make_guest_token(token_use="access")))
    assert payload["tier"] == "guest"
    assert payload["guest_id"] == "abc123"


def test_require_any_token_rejects_guest_refresh_token():
    from backend.auth.guards import require_any_token
    with pytest.raises(UnauthorizedError):
        require_any_token.impl(_creds(make_guest_token(token_use="refresh")))


def test_require_any_token_rejects_garbage_token():
    from backend.auth.guards import require_any_token
    with pytest.raises(UnauthorizedError):
        require_any_token.impl(_creds("not-a-jwt"))


def test_require_any_token_rejects_expired_guest_token():
    from backend.auth.guards import require_any_token
    with pytest.raises(UnauthorizedError):
        require_any_token.impl(_creds(make_guest_token(exp_offset=-10)))


def test_require_any_token_rejects_missing_exp():
    from backend.auth.guards import require_any_token
    with pytest.raises(UnauthorizedError):
        require_any_token.impl(_creds(make_guest_token(exp_offset=None)))


def test_require_any_token_rejects_no_authorization_header_at_all():
    """No credentials at all (bearer's auto_error=False lets this reach us as None)
    must still raise UnauthorizedError -> the standard ErrorResponse shape, not
    FastAPI's own auto-error {"detail": "Not authenticated"} (018-public-api-auth FR-008)."""
    from backend.auth.guards import require_any_token
    with pytest.raises(UnauthorizedError):
        require_any_token.impl(None)


def test_require_admin_rejects_no_authorization_header_at_all():
    from backend.auth.guards import require_admin
    with pytest.raises(UnauthorizedError):
        require_admin.impl(None)


def test_require_user_rejects_no_authorization_header_at_all():
    from backend.auth.guards import require_user
    with pytest.raises(UnauthorizedError):
        require_user.impl(None)
