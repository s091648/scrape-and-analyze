from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone
import uuid

ScraperBase = declarative_base()


class ScraperSetting(ScraperBase):
    __tablename__ = 'scraper_settings'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    url = Column(Text, nullable=False)
    frequency = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    selector_config = Column(JSONB)
    last_scraped_at = Column(DateTime(timezone=True), nullable=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey('topics.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
