from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime, timezone
import uuid

from models.base import Base


class FailedTask(Base):
    __tablename__ = 'failed_tasks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type = Column(String(50), nullable=False)
    article_url = Column(Text)
    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id'))
    analysis_id = Column(UUID(as_uuid=True), ForeignKey('analyses.id', ondelete='SET NULL'), nullable=True)
    exception_type = Column(String(200))
    exception_message = Column(Text)
    context = Column(JSONB, nullable=True)
    traceback = Column(Text, nullable=True)
    failed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index('idx_failed_tasks_resolved', 'resolved'),
        Index('idx_failed_tasks_failed_at', 'failed_at'),
    )
