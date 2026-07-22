from sqlalchemy import Column, String, Text, ForeignKey, UniqueConstraint, Index, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from models.base import Base
from models.db_schema import DbSchema


class TagsTranslation(Base):
    __tablename__ = 'tags_translation'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tag_id = Column(UUID(as_uuid=True), ForeignKey('intelligence.tags.id'), nullable=False)
    language = Column(String(10), nullable=False)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tag = relationship('Tag', backref='translations')

    __table_args__ = (
        UniqueConstraint('tag_id', 'language', name='uq_tags_translation_tag_language'),
        Index('idx_tags_translation_tag_id', 'tag_id'),
        Index('idx_tags_translation_language', 'language'),
        {'schema': DbSchema.INTELLIGENCE.value},
    )
