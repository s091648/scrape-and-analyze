from typing import Literal, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class SelectorConfig(BaseModel):
    article_link: str
    title: str
    content: str


class ScraperSettingCreate(BaseModel):
    source_type: Literal["rss", "blog"]
    name: str
    url: str
    frequency: Literal["daily", "weekly"]
    is_active: bool = True
    selector_config: Optional[SelectorConfig] = None


class ScraperSettingUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    frequency: Optional[Literal["daily", "weekly"]] = None
    is_active: Optional[bool] = None
    selector_config: Optional[SelectorConfig] = None


class ScraperSettingOut(BaseModel):
    id: UUID
    source_type: str
    name: str
    url: str
    frequency: str
    is_active: bool
    selector_config: Optional[SelectorConfig] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
