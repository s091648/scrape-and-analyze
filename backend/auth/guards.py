import os
import time
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

bearer = HTTPBearer()


def _require_admin_impl(token: HTTPAuthorizationCredentials) -> dict:
    secret = os.environ.get("NEXTAUTH_SECRET", "")
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
