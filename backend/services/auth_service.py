import uuid as _uuid
from datetime import datetime, timezone
from uuid import UUID

import bcrypt
from sqlalchemy.orm import Session

from backend.schemas.user import AdminUpdateUserRequest


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
