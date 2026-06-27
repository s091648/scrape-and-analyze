from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, Integer, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base


class ArticleMetrics(Base):
    __tablename__ = 'article_metrics'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='CASCADE'), nullable=False)
    citation_count = Column(Integer, nullable=True)
    view_count = Column(Integer, nullable=False, default=0)
    last_flushed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint('article_id', name='uq_article_metrics_article_id'),
    )
