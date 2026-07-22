from typing import Literal, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


class UserOut(BaseModel):
    id: UUID
    email: Optional[str] = None
    name: Optional[str] = None
    username: Optional[str] = None
    role: str
    is_allowed: bool
    icon: Optional[str] = None
    google_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RegisterCredentialsRequest(BaseModel):
    username: str
    password: str
    email: EmailStr
    name: Optional[str] = None


class RegisterGoogleRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    google_id: str


class AdminCreateUserRequest(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = None
    name: Optional[str] = None
    role: Literal['admin', 'user'] = 'user'


class AdminUpdateUserRequest(BaseModel):
    role: Optional[Literal['admin', 'user']] = None
    is_allowed: Optional[bool] = None
    name: Optional[str] = None
    email: Optional[EmailStr] = None


class GoogleAuthorizeRequest(BaseModel):
    email: EmailStr
    google_id: str
    name: Optional[str] = None


class UserProfileOut(BaseModel):
    id: UUID
    email: Optional[str] = None
    name: Optional[str] = None
    username: Optional[str] = None
    role: str
    icon: Optional[str] = None
    google_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class LinkGoogleRequest(BaseModel):
    google_id: str
