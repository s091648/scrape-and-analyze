from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class TopicCreate(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    color_hex: Optional[str] = None
    prompt_override: Optional[str] = None
    sort_order: Optional[int] = None


class TopicUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    color_hex: Optional[str] = None
    prompt_override: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class TopicOut(BaseModel):
    id: UUID
    name: str
    display_name: str
    description: Optional[str] = None
    color_hex: Optional[str] = None
    prompt_override: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
