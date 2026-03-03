from typing import Literal, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class UserOut(BaseModel):
    id: UUID
    email: Optional[str] = None
    name: Optional[str] = None
    username: Optional[str] = None
    role: str
    is_allowed: bool
    google_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RegisterCredentialsRequest(BaseModel):
    username: str
    password: str
    email: str
    name: Optional[str] = None


class RegisterGoogleRequest(BaseModel):
    email: str
    name: Optional[str] = None
    google_id: str


class AdminCreateUserRequest(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    name: Optional[str] = None
    role: Literal['admin', 'user'] = 'user'


class AdminUpdateUserRequest(BaseModel):
    role: Optional[Literal['admin', 'user']] = None
    is_allowed: Optional[bool] = None
    name: Optional[str] = None
    email: Optional[str] = None


class GoogleAuthorizeRequest(BaseModel):
    email: str
    google_id: str
    name: Optional[str] = None
