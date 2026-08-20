from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from models.types import SelectorConfigColumn
from models.base import Base
from models.db_schema import DbSchema

ScraperBase = Base


class ScraperSetting(Base):
    __tablename__ = 'scraper_settings'
    __table_args__ = {'schema': DbSchema.COLLECTION.value}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    url = Column(Text, nullable=False)
    frequency = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    selector_config = Column(SelectorConfigColumn, nullable=True)
    last_scraped_at = Column(DateTime(timezone=True), nullable=True)
    # fk_scraper_settings_topic_id — added by migration 12, never dropped, still live in
    # Postgres today. The ORM model was missing the ForeignKey() declaration even though
    # the DB-level constraint always existed (found via 023-article-search's models/ audit).
    topic_id = Column(UUID(as_uuid=True), ForeignKey('core.topics.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
