import time
from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from backend.config import NEXTAUTH_SECRET

bearer = HTTPBearer()
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
        sub = payload.get("sub")
        return UUID(sub) if sub else None
    except (JWTError, ValueError):
        return None


def _require_admin_impl(token: HTTPAuthorizationCredentials) -> dict:
    secret = NEXTAUTH_SECRET
    try:
        payload = jwt.decode(token.credentials, secret, algorithms=["HS256"],
                             options={"verify_exp": False})
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if "exp" not in payload:
        raise HTTPException(status_code=401, detail="Token missing exp claim")
    if payload["exp"] < int(time.time()):
        raise HTTPException(status_code=401, detail="Token expired")
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    return payload


def require_admin(token: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    return _require_admin_impl(token)


# Expose implementation for direct testing (avoids inspect.signature() following __wrapped__)
require_admin.impl = _require_admin_impl


def _require_user_impl(token: HTTPAuthorizationCredentials) -> dict:
    secret = NEXTAUTH_SECRET
    try:
        payload = jwt.decode(token.credentials, secret, algorithms=["HS256"],
                             options={"verify_exp": False})
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if "exp" not in payload:
        raise HTTPException(status_code=401, detail="Token missing exp claim")
    if payload["exp"] < int(time.time()):
        raise HTTPException(status_code=401, detail="Token expired")

    return payload


def require_user(token: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    return _require_user_impl(token)


require_user.impl = _require_user_impl
