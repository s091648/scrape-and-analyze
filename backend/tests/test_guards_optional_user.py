"""Unit tests for backend.auth.guards.get_optional_user_id"""
import os
import time
import uuid

from jose import jwt

SECRET = "test-secret"  # matches conftest.py NEXTAUTH_SECRET
os.environ["NEXTAUTH_SECRET"] = SECRET


def make_token(sub="admin", exp_offset=3600, include_exp=True):
    payload = {"sub": sub}
    if include_exp:
        payload["exp"] = int(time.time()) + exp_offset
    return jwt.encode(payload, SECRET, algorithm="HS256")


def test_no_token_returns_none():
    from backend.auth.guards import get_optional_user_id
    result = get_optional_user_id(token=None)
    assert result is None


def test_valid_token_returns_user_id():
    from backend.auth.guards import get_optional_user_id
    from fastapi.security import HTTPAuthorizationCredentials
    user_id = uuid.uuid4()
    token = make_token(sub=str(user_id))
    result = get_optional_user_id(token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert result == user_id


def test_expired_token_returns_none():
    from backend.auth.guards import get_optional_user_id
    from fastapi.security import HTTPAuthorizationCredentials
    token = make_token(sub=str(uuid.uuid4()), exp_offset=-10)
    result = get_optional_user_id(token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert result is None


def test_missing_exp_claim_returns_none():
    from backend.auth.guards import get_optional_user_id
    from fastapi.security import HTTPAuthorizationCredentials
    token = make_token(sub=str(uuid.uuid4()), include_exp=False)
    result = get_optional_user_id(token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert result is None


def test_missing_sub_returns_none():
    from backend.auth.guards import get_optional_user_id
    from fastapi.security import HTTPAuthorizationCredentials
    payload = {"exp": int(time.time()) + 3600}
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    result = get_optional_user_id(token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert result is None


def test_non_uuid_sub_returns_none():
    from backend.auth.guards import get_optional_user_id
    from fastapi.security import HTTPAuthorizationCredentials
    token = make_token(sub="not-a-uuid")
    result = get_optional_user_id(token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert result is None


def test_malformed_token_returns_none():
    from backend.auth.guards import get_optional_user_id
    from fastapi.security import HTTPAuthorizationCredentials
    result = get_optional_user_id(token=HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-jwt"))
    assert result is None


def test_wrong_secret_returns_none():
    from backend.auth.guards import get_optional_user_id
    from fastapi.security import HTTPAuthorizationCredentials
    token = jwt.encode({"sub": str(uuid.uuid4()), "exp": int(time.time()) + 3600}, "wrong-secret", algorithm="HS256")
    result = get_optional_user_id(token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert result is None
