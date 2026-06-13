from typing import Literal, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class RagEmbeddingProviderCreate(BaseModel):
    role: Literal['dense', 'sparse']
    provider_type: Literal['endpoint', 'local']
    model: Optional[str] = Field(default=None, min_length=1)
    endpoint_url: Optional[str] = Field(default=None, min_length=1)
    api_key_env: Optional[str] = Field(default=None, min_length=1)
    dimension: int = Field(ge=1)
    is_active: bool = True
    rpm: Optional[int] = Field(default=None, ge=0)
    tpm: Optional[int] = Field(default=None, ge=0)
    rpd: Optional[int] = Field(default=None, ge=0)


class RagEmbeddingProviderUpdate(BaseModel):
    role: Optional[Literal['dense', 'sparse']] = None
    provider_type: Optional[Literal['endpoint', 'local']] = None
    model: Optional[str] = Field(default=None, min_length=1)
    endpoint_url: Optional[str] = Field(default=None, min_length=1)
    api_key_env: Optional[str] = Field(default=None, min_length=1)
    dimension: Optional[int] = Field(default=None, ge=1)
    is_active: Optional[bool] = None
    rpm: Optional[int] = Field(default=None, ge=0)
    tpm: Optional[int] = Field(default=None, ge=0)
    rpd: Optional[int] = Field(default=None, ge=0)


class RagEmbeddingProviderOut(BaseModel):
    id: UUID
    role: str
    provider_type: str
    model: Optional[str] = None
    endpoint_url: Optional[str] = None
    api_key_env: Optional[str] = None
    dimension: int
    is_active: bool
    rpm: Optional[int] = None
    tpm: Optional[int] = None
    rpd: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
