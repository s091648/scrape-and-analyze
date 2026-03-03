from fastapi import APIRouter, Depends, HTTPException
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


def _get_user_by_username(db: Session, username: str):
    from backend.models.auth import User
    return db.query(User).filter(User.username == username).first()


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
