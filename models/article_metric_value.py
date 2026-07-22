from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Numeric, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base
from models.db_schema import DbSchema


class ArticleMetricValue(Base):
    __tablename__ = 'article_metric_values'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id = Column(UUID(as_uuid=True), ForeignKey('core.articles.id', ondelete='CASCADE'), nullable=False)
    metric_key = Column(String(50), nullable=False)
    value = Column(Numeric, nullable=True)
    last_flushed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint('article_id', 'metric_key', name='uq_article_metric_values_article_id_metric_key'),
        {'schema': DbSchema.COLLECTION.value},
    )
