from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from models.base import Base
from models.db_schema import DbSchema


class Analysis(Base):
    __tablename__ = 'analyses'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id = Column(UUID(as_uuid=True), ForeignKey('core.articles.id'), unique=True, nullable=False)
    correlation_id = Column(UUID(as_uuid=True), nullable=False)
    analyzed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    model_used = Column(String(100), nullable=False)
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)

    article = relationship("Article", backref="analyses")

    __table_args__ = (
        Index('idx_analyses_article_id', 'article_id'),
        Index('idx_analyses_analyzed_at', 'analyzed_at'),
        {'schema': DbSchema.INTELLIGENCE.value},
    )
