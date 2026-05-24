from sqlalchemy import Column, String, Text, ForeignKey, UniqueConstraint, Index, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref
import uuid

from models.base import Base


class TagGroupDefinitionsTranslation(Base):
    __tablename__ = 'tag_group_definitions_translation'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tag_group_definition_id = Column(UUID(as_uuid=True), ForeignKey('tag_group_definitions.id'), nullable=False)
    language = Column(String(10), nullable=False)
    display_name = Column(String(200), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    group_def = relationship('TagGroupDefinition', backref=backref('translations', cascade='all, delete-orphan'))

    __table_args__ = (
        UniqueConstraint('tag_group_definition_id', 'language', name='uq_tag_group_definitions_translation_group_language'),
        Index('idx_tag_group_definitions_translation_group_id', 'tag_group_definition_id'),
        Index('idx_tag_group_definitions_translation_language', 'language'),
    )
