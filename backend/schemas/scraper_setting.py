from typing import Any, Literal, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, field_validator


class ScraperSettingCreate(BaseModel):
    source_type: Literal["rss", "blog", "arxiv", "semantic_scholar", "openalex"]
    name: str
    url: str = ""
    frequency: int
    is_active: bool = True
    selector_config: Optional[dict] = None
    topic_id: UUID


class ScraperSettingUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    frequency: Optional[int] = None
    is_active: Optional[bool] = None
    selector_config: Optional[dict] = None
    topic_id: Optional[UUID] = None


class ScraperSettingOut(BaseModel):
    id: UUID
    source_type: str
    name: str
    url: str
    frequency: int
    is_active: bool
    selector_config: Optional[dict] = None
    last_scraped_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    topic_id: UUID
    activity: list[int] = []

    @field_validator("selector_config", mode="before")
    @classmethod
    def coerce_selector_config(cls, v: Any) -> Any:
        if v is not None and isinstance(v, BaseModel):
            return v.model_dump()
        return v

    class Config:
        from_attributes = True
