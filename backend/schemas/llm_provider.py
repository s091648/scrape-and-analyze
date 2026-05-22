from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class LlmProviderCreate(BaseModel):
    name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    api_key_env: str = Field(min_length=1)
    priority: int = Field(ge=1)
    is_active: bool = True
    rpm: Optional[int] = Field(default=None, ge=0)
    tpm: Optional[int] = Field(default=None, ge=0)
    rpd: Optional[int] = Field(default=None, ge=0)


class LlmProviderUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    model: Optional[str] = Field(default=None, min_length=1)
    api_key_env: Optional[str] = Field(default=None, min_length=1)
    priority: Optional[int] = Field(default=None, ge=1)
    is_active: Optional[bool] = None
    rpm: Optional[int] = Field(default=None, ge=0)
    tpm: Optional[int] = Field(default=None, ge=0)
    rpd: Optional[int] = Field(default=None, ge=0)


class ProviderReorderItem(BaseModel):
    id: UUID
    priority: int


class LlmProviderReorder(BaseModel):
    order: list[ProviderReorderItem]


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