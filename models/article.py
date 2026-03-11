from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone
import uuid

Base = declarative_base()


class Article(Base):
    __tablename__ = 'articles'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(Text, unique=True, nullable=False)
    url_hash = Column(String(64), nullable=False)
    source = Column(String(50), nullable=False)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    published_at = Column(DateTime(timezone=True))
    scraped_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    metadata_ = Column('metadata', JSONB)
    correlation_id = Column(UUID(as_uuid=True), nullable=False)

    __table_args__ = (
        Index('idx_articles_url_hash', 'url_hash'),
        Index('idx_articles_source', 'source'),
        Index('idx_articles_scraped_at', 'scraped_at'),
    )
