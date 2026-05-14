from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class LlmProviderCreate(BaseModel):
    name: str
    model: str
    api_key_env: str
    priority: int
    is_active: bool = True
    rpm: Optional[int] = None
    tpm: Optional[int] = None
    rpd: Optional[int] = None


class LlmProviderUpdate(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    api_key_env: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    rpm: Optional[int] = None
    tpm: Optional[int] = None
    rpd: Optional[int] = None


class LlmProviderOut(BaseModel):
    id: UUID
    name: str
    model: str
    api_key_env: str
    priority: int
    is_active: bool
    rpm: Optional[int] = None
    tpm: Optional[int] = None
    rpd: Optional[int] = None
    usage_24h: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True