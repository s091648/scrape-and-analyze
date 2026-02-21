import os
import time
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

NEXTAUTH_SECRET = os.environ.get("NEXTAUTH_SECRET", "")
bearer = HTTPBearer()


def require_admin(token: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        payload = jwt.decode(token.credentials, NEXTAUTH_SECRET, algorithms=["HS256"],
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


# Expose the function without Depends wrapping for direct testing
require_admin.__wrapped__ = require_admin
