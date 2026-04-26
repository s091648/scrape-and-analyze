from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from models.base import Base


class ScraperKeyword(Base):
    __tablename__ = 'scraper_keywords'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(
        UUID(as_uuid=True),
        ForeignKey('topics.id', ondelete='CASCADE'),
        nullable=False,
    )
    # Discriminates the keyword variant: 'rss' | 'arxiv_keyword' | 'arxiv_category'
    keyword_type = Column(String(30), nullable=False, default='rss')
    keyword = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('topic_id', 'keyword_type', 'keyword', name='uq_scraper_keyword_topic_type_keyword'),
    )
