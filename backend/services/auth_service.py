import hashlib
import time
import uuid as _uuid
from datetime import datetime, timezone
from uuid import UUID

import bcrypt
from fastapi import Request
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from src.shared.domain.exceptions import UnauthorizedError
from backend.config import NEXTAUTH_SECRET
from backend.schemas.user import AdminUpdateUserRequest

GUEST_ACCESS_TOKEN_TTL_SECONDS = 60 * 60
GUEST_REFRESH_TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60


def get_user_by_username(db: Session, username: str):
    from models.auth import User
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str):
    from models.auth import User
    return db.query(User).filter(User.email == email).first()


def get_user_by_google_id(db: Session, google_id: str):
    from models.auth import User
    return db.query(User).filter(User.google_id == google_id).first()


def get_user_by_id(db: Session, user_id: UUID):
    from models.auth import User
    return db.query(User).filter(User.id == user_id).first()


def list_users(db: Session):
    from models.auth import User
    return db.query(User).order_by(User.created_at.desc()).all()


def create_user(db: Session, **kwargs):
    from models.auth import User
    user = User(**kwargs)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user, data: AdminUpdateUserRequest):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user) -> None:
    db.delete(user)
    db.commit()


def update_google_id(db: Session, user, google_id: str) -> None:
    user.google_id = google_id
    user.updated_at = datetime.now(timezone.utc)
    db.commit()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def compute_guest_id(request: Request) -> str:
    """Stable per-visitor identifier derived from IP + User-Agent (research.md §3),
    reused verbatim from chat.py's pre-existing ip-hash logic."""
    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    user_agent = request.headers.get("user-agent", "")
    return hashlib.sha256(f"{client_ip}{user_agent}".encode()).hexdigest()[:16]


def _create_guest_token(guest_id: str, token_use: str, ttl_seconds: int) -> str:
    claims = {
        "tier": "guest",
        "guest_id": guest_id,
        "token_use": token_use,
        "exp": int(time.time()) + ttl_seconds,
    }
    return jwt.encode(claims, NEXTAUTH_SECRET, algorithm="HS256")


def create_guest_access_token(guest_id: str) -> str:
    return _create_guest_token(guest_id, "access", GUEST_ACCESS_TOKEN_TTL_SECONDS)


def create_guest_refresh_token(guest_id: str) -> str:
    return _create_guest_token(guest_id, "refresh", GUEST_REFRESH_TOKEN_TTL_SECONDS)


def decode_guest_refresh_token(token: str) -> dict:
    """Validate a guest refresh token for POST /auth/guest/refresh. Raises
    UnauthorizedError for anything malformed, expired, or not a refresh token —
    including an access token presented here by mistake (contracts/guest-token.md)."""
    try:
        payload = jwt.decode(token, NEXTAUTH_SECRET, algorithms=["HS256"],
                             options={"verify_exp": False})
    except JWTError:
        raise UnauthorizedError("Invalid token")

    if "exp" not in payload:
        raise UnauthorizedError("Token missing exp claim")
    if payload["exp"] < int(time.time()):
        raise UnauthorizedError("Token expired")
    if payload.get("tier") != "guest" or payload.get("token_use") != "refresh":
        raise UnauthorizedError("Token not accepted for this endpoint")

    return payload
