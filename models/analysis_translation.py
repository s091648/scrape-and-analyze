from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from models.base import Base


class AnalysisTranslation(Base):
    __tablename__ = 'analysis_translations'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey('analyses.id', ondelete='CASCADE'), nullable=False)
    language = Column(String(10), nullable=False)
    summary = Column(Text)
    pain_points = Column(Text)
    insights = Column(Text)
    innovations = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    analysis = relationship("Analysis", backref="analysis_translations")

    __table_args__ = (
        Index('idx_analysis_translations_analysis_id', 'analysis_id'),
        Index('idx_analysis_translations_language', 'language'),
        UniqueConstraint('analysis_id', 'language', name='uq_analysis_translations_analysis_language'),
    )
