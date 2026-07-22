from enum import Enum
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class TagMode(str, Enum):
    unsupervised = 'unsupervised'
    semi_supervised = 'semi_supervised'
    supervised = 'supervised'


class TopicCreate(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    color_hex: Optional[str] = None
    prompt_override: Optional[str] = None
    sort_order: Optional[int] = None
    tag_mode: TagMode = TagMode.unsupervised


class TopicUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    color_hex: Optional[str] = None
    prompt_override: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    tag_mode: Optional[TagMode] = None


class TopicOut(BaseModel):
    id: UUID
    name: str
    display_name: str
    description: Optional[str] = None
    color_hex: Optional[str] = None
    prompt_override: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: bool
    tag_mode: TagMode
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
