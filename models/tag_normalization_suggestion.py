from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from models.base import Base


class TagNormalizationSuggestion(Base):
    __tablename__ = 'tag_normalization_suggestions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    new_tag_id = Column(UUID(as_uuid=True), ForeignKey('tags.id', ondelete='CASCADE'), nullable=False)
    existing_tag_id = Column(UUID(as_uuid=True), ForeignKey('tags.id', ondelete='CASCADE'), nullable=False)
    similarity_score = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='SET NULL'), nullable=True)
    created_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(UUID(as_uuid=True), nullable=True)

    new_tag = relationship('Tag', foreign_keys=[new_tag_id])
    existing_tag = relationship('Tag', foreign_keys=[existing_tag_id])

    __table_args__ = (
        Index('idx_tns_status', 'status'),
        Index('idx_tns_new_tag_id', 'new_tag_id'),
    )
