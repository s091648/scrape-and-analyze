import time
from typing import Optional
from uuid import UUID
from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from shared.domain.exceptions import UnauthorizedError, ForbiddenError
from backend.config import NEXTAUTH_SECRET

bearer = HTTPBearer(auto_error=False)
optional_bearer = HTTPBearer(auto_error=False)


def get_optional_user_id(token: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer)) -> Optional[UUID]:
    """Extract user_id from JWT if present and valid; return None for unauthenticated requests."""
    if not token:
        return None
    secret = NEXTAUTH_SECRET
    try:
        payload = jwt.decode(token.credentials, secret, algorithms=["HS256"], options={"verify_exp": False})
        if payload.get("exp", 0) < int(time.time()):
            return None
        if payload.get("token_use") == "refresh":
            return None
        sub = payload.get("sub")
        return UUID(sub) if sub else None
    except (JWTError, ValueError):
        return None


def _require_admin_impl(token: Optional[HTTPAuthorizationCredentials]) -> dict:
    if token is None:
        raise UnauthorizedError("Missing Authorization header")
    secret = NEXTAUTH_SECRET
    try:
        payload = jwt.decode(token.credentials, secret, algorithms=["HS256"],
                             options={"verify_exp": False})
    except JWTError:
        raise UnauthorizedError("Invalid token")

    if "exp" not in payload:
        raise UnauthorizedError("Token missing exp claim")
    if payload["exp"] < int(time.time()):
        raise UnauthorizedError("Token expired")
    if payload.get("token_use") == "refresh":
        raise UnauthorizedError("A refresh token is not accepted for this endpoint")
    if payload.get("role") != "admin":
        raise ForbiddenError("Admin role required")

    return payload


def require_admin(token: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> dict:
    return _require_admin_impl(token)


# Expose implementation for direct testing (avoids inspect.signature() following __wrapped__)
require_admin.impl = _require_admin_impl


def _require_user_impl(token: Optional[HTTPAuthorizationCredentials]) -> dict:
    if token is None:
        raise UnauthorizedError("Missing Authorization header")
    secret = NEXTAUTH_SECRET
    try:
        payload = jwt.decode(token.credentials, secret, algorithms=["HS256"],
                             options={"verify_exp": False})
    except JWTError:
        raise UnauthorizedError("Invalid token")

    if "exp" not in payload:
        raise UnauthorizedError("Token missing exp claim")
    if payload["exp"] < int(time.time()):
        raise UnauthorizedError("Token expired")
    # A guest access token (018-public-api-auth) is a valid, non-expired token but
    # is not "a specific logged-in user" — endpoints requiring require_user must
    # keep refusing it, exactly as they refuse having no token at all (FR-003).
    if payload.get("tier") == "guest":
        raise UnauthorizedError("A guest token is not accepted for this endpoint")
    # A real user's own refresh token (POST /auth/refresh) is signed with the same
    # secret and carries a `sub` claim but no `role` — without this check it would
    # otherwise sail through as "not guest tier" and be treated as a valid session.
    if payload.get("token_use") == "refresh":
        raise UnauthorizedError("A refresh token is not accepted for this endpoint")

    return payload


def require_user(token: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> dict:
    return _require_user_impl(token)


require_user.impl = _require_user_impl


def _require_any_token_impl(token: Optional[HTTPAuthorizationCredentials]) -> dict:
    if token is None:
        raise UnauthorizedError("Missing Authorization header")
    secret = NEXTAUTH_SECRET
    try:
        payload = jwt.decode(token.credentials, secret, algorithms=["HS256"],
                             options={"verify_exp": False})
    except JWTError:
        raise UnauthorizedError("Invalid token")

    if "exp" not in payload:
        raise UnauthorizedError("Token missing exp claim")
    if payload["exp"] < int(time.time()):
        raise UnauthorizedError("Token expired")
    if payload.get("token_use") == "refresh":
        raise UnauthorizedError("A refresh token is not accepted for this endpoint")

    # Accepts either an existing real user/admin token (has a `role` claim, exactly
    # what require_user already accepts) or a guest *access* token — never a guest
    # *refresh* token, which must only ever be exchanged via /auth/guest/refresh.
    if "role" in payload:
        return payload
    if payload.get("tier") == "guest" and payload.get("token_use", "access") == "access":
        return payload
    raise UnauthorizedError("Token not accepted for this endpoint")


def require_any_token(token: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> dict:
    return _require_any_token_impl(token)


require_any_token.impl = _require_any_token_impl
