from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict


class ArticleSourceOut(BaseModel):
    id: UUID
    title: str
    url: str
    public_article_id: UUID


class WeeklyReportOut(BaseModel):
    id: UUID
    topic_id: Optional[UUID]
    week_start_date: date
    title: str
    summary_text: str
    cover_image_url: Optional[str]
    article_count: int
    status: str
    created_at: Optional[datetime]
    sources: List[ArticleSourceOut] = []

    model_config = ConfigDict(from_attributes=True)


class PaginatedWeeklyReports(BaseModel):
    items: List[WeeklyReportOut]
    total: int
    page: int
    size: int


class WeeklyReportWeeksOut(BaseModel):
    weeks: List[date]
