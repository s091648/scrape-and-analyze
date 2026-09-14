from datetime import date
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class DailyViews(BaseModel):
    day: date
    views: int


class TrendingArticle(BaseModel):
    article_id: UUID
    title: str
    source: Optional[str] = None
    topic: Optional[str] = None
    window_views: int
    total_views: int
    sparkline: List[DailyViews]


class TopicViews(BaseModel):
    topic: str
    views: int


class AllTimeTopArticle(BaseModel):
    article_id: UUID
    title: str
    source: Optional[str] = None
    topic: Optional[str] = None
    total_views: int


class AnalyticsOverview(BaseModel):
    """/admin/analytics/overview response — one payload for the whole page.

    `daily_totals` and `by_topic` cover the last `days` UTC days; `trending` is the top 20 by
    views in that window, each with a per-day `sparkline` over the same window; `all_time_top`
    is from article_metrics.view_count and has no window.
    """
    days: int
    daily_totals: List[DailyViews]
    trending: List[TrendingArticle]
    by_topic: List[TopicViews]
    all_time_top: List[AllTimeTopArticle]
