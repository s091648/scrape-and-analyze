from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Text, Integer, Date, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from models.base import Base
from models.db_schema import DbSchema


class WeeklyReport(Base):
    __tablename__ = 'weekly_reports'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(UUID(as_uuid=True), ForeignKey('core.topics.id', ondelete='SET NULL'), nullable=True)
    week_start_date = Column(Date, nullable=False)
    title = Column(Text, nullable=False)
    summary_text = Column(Text, nullable=False)
    cover_image_url = Column(Text, nullable=True)
    article_ids = Column(JSONB, nullable=False, default=list)
    article_count = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default='pending')
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint('topic_id', 'week_start_date', name='uq_weekly_reports_topic_week'),
        {'schema': DbSchema.INTELLIGENCE.value},
    )
