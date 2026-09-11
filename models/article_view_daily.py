import uuid

from sqlalchemy import Column, Integer, Date, Index, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base
from models.db_schema import DbSchema


class ArticleViewDaily(Base):
    """One row per (article, UTC day) holding that day's *delta* of article-detail views.

    Written by backend/services/article_service.py::flush_view_counts() in the same loop that
    bumps the cumulative article_metrics.view_count — an upsert that adds the flushed batch to
    the current day's bucket. `article_metrics.view_count` stays the authoritative all-time
    total; this table is purely the time-windowed history behind the /admin/analytics page
    ("trending in the last N days", per-article sparklines, daily totals).

    Daily granularity is deliberate: a view is already IP-deduplicated over 24h
    (backend/routers/articles.py::record_article_view), so sub-day resolution carries little
    signal, and content trends are a days-to-weeks phenomenon. History only exists from the
    day this ships — the cumulative counter can't be back-projected into a daily distribution.
    """

    __tablename__ = "article_view_daily"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    day = Column(Date, nullable=False)
    views = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("article_id", "day", name="uq_article_view_daily_article_day"),
        Index("idx_article_view_daily_day", "day"),
        {"schema": DbSchema.COLLECTION.value},
    )
