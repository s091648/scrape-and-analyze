from typing import Dict, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ArticleTagGroupOut(BaseModel):
    group_name: str
    display_name: str
    color: Optional[str] = None
    tags: list[str]


class ArticleOut(BaseModel):
    id: UUID
    url: str
    source: str
    title: str
    content: str
    published_at: Optional[datetime]
    scraped_at: Optional[datetime]
    via_source: Optional[str] = None
    original_source: Optional[str] = None
    translated_title: Optional[str] = None
    translated_content: Optional[str] = None
    has_vectors: bool = False
    metrics: Dict[str, float] = {}
    view_count: int = 0
    is_favorited: bool = False
    # Only ever set by search_articles_hybrid (True/False) — None for every other endpoint
    # that returns ArticleOut (e.g. GET /articles), where "exact match" isn't a meaningful
    # concept since there's no query to match against.
    exact_match: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedArticles(BaseModel):
    items: list[ArticleOut]
    total: int
    page: int
    size: int


class ArticleDetailOut(BaseModel):
    id: UUID
    url: str
    source: str
    title: str
    content: str
    published_at: Optional[datetime]
    scraped_at: Optional[datetime]
    via_source: Optional[str] = None
    original_source: Optional[str] = None
    tags: list[str] = []
    tag_groups: list[ArticleTagGroupOut] = []
    pain_points: Optional[str] = None
    insights: Optional[str] = None
    innovations: Optional[str] = None
    model_used: Optional[str] = None
    translated_title: Optional[str] = None
    translated_content: Optional[str] = None
    has_vectors: bool = False
    metrics: Dict[str, float] = {}
    view_count: int = 0

    model_config = ConfigDict(from_attributes=True)
