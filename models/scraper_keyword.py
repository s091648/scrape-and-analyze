from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from models.scraper_setting import ScraperBase


class ScraperKeyword(ScraperBase):
    __tablename__ = 'scraper_keywords'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scraper_setting_id = Column(
        UUID(as_uuid=True),
        ForeignKey('scraper_settings.id', ondelete='CASCADE'),
        nullable=False,
    )
    keyword = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('scraper_setting_id', 'keyword', name='uq_scraper_keyword_setting_keyword'),
    )
