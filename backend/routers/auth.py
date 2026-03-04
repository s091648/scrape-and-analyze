import uuid as _uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
import bcrypt

from backend.database import get_db
from backend.auth.guards import require_admin
from backend.schemas.user import (
    UserOut, RegisterCredentialsRequest, RegisterGoogleRequest,
    AdminCreateUserRequest, AdminUpdateUserRequest, GoogleAuthorizeRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

from pydantic import BaseModel


class _LoginRequest(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------------------------
# Helper DB functions
# ---------------------------------------------------------------------------

def _get_user_by_username(db: Session, username: str):
    from backend.models.auth import User
    return db.query(User).filter(User.username == username).first()


def _get_user_by_email(db: Session, email: str):
    from backend.models.auth import User
    return db.query(User).filter(User.email == email).first()


def _get_user_by_google_id(db: Session, google_id: str):
    from backend.models.auth import User
    return db.query(User).filter(User.google_id == google_id).first()


def _get_user_by_id(db: Session, user_id: UUID):
    from backend.models.auth import User
    return db.query(User).filter(User.id == user_id).first()


def _create_user(db: Session, **kwargs) -> "User":
    from backend.models.auth import User
    user = User(**kwargs)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _update_google_id(db: Session, user, google_id: str):
    user.google_id = google_id
    user.updated_at = datetime.now(timezone.utc)
    db.commit()


def _list_users(db: Session):
    from backend.models.auth import User
    return db.query(User).order_by(User.created_at.desc()).all()


def _update_user(db: Session, user, data: AdminUpdateUserRequest):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def _delete_user(db: Session, user):
    db.delete(user)
    db.commit()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/verify")
def verify_credentials(data: _LoginRequest, db: Session = Depends(get_db)):
    user = _get_user_by_username(db, data.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not bcrypt.checkpw(data.password.encode(), user.hashed_password.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_allowed:
        raise HTTPException(status_code=403, detail="Account disabled")
    return {"id": str(user.id), "username": user.username, "email": user.email,
            "name": user.name, "role": user.role}


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: dict, db: Session = Depends(get_db)):
    """
    Accept either RegisterCredentialsRequest or RegisterGoogleRequest.
    Distinguish by presence of 'google_id' key.
    """
    try:
        if "google_id" in data:
            req = RegisterGoogleRequest(**data)
            new_user = _create_user(
                db,
                id=_uuid.uuid4(),
                email=req.email,
                name=req.name,
                google_id=req.google_id,
                role='user',
                is_allowed=True,
            )
        else:
            req = RegisterCredentialsRequest(**data)
            hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
            new_user = _create_user(
                db,
                id=_uuid.uuid4(),
                email=req.email,
                name=req.name,
                username=req.username,
                hashed_password=hashed,
                role='user',
                is_allowed=True,
            )
        return new_user
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Email or username already taken")
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/google/authorize", response_model=UserOut)
def google_authorize(data: GoogleAuthorizeRequest, db: Session = Depends(get_db)):
    """Called by NextAuth signIn callback for google-login provider."""
    user = _get_user_by_email(db, data.email)
    if not user:
        raise HTTPException(status_code=404, detail="Email not registered")
    if not user.is_allowed:
        raise HTTPException(status_code=403, detail="Account disabled")
    if not user.google_id:
        _update_google_id(db, user, data.google_id)
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(require_admin)):
    return _list_users(db)


@router.post("/users", response_model=UserOut, status_code=201)
def admin_create_user(data: AdminCreateUserRequest, db: Session = Depends(get_db),
                      _=Depends(require_admin)):
    if not data.email and not data.username:
        raise HTTPException(status_code=422, detail="email or username required")
    kwargs = {
        "id": _uuid.uuid4(),
        "email": data.email,
        "name": data.name,
        "role": data.role,
        "is_allowed": True,
    }
    if data.username and data.password:
        kwargs["username"] = data.username
        kwargs["hashed_password"] = bcrypt.hashpw(
            data.password.encode(), bcrypt.gensalt()
        ).decode()
    try:
        return _create_user(db, **kwargs)
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Email or username already taken")
        raise


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: UUID, data: AdminUpdateUserRequest,
                db: Session = Depends(get_db), _=Depends(require_admin)):
    user = _get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _update_user(db, user, data)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: UUID, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = _get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _delete_user(db, user)
    return Response(status_code=204)
