from sqlalchemy import Column, String, Text, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base
import uuid


class TagGroupDefinition(Base):
    __tablename__ = 'tag_group_definitions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)           # no longer globally unique
    display_name = Column(String(100), nullable=False)
    description = Column(Text)
    color_hex = Column(String(7))
    sort_order = Column(Integer)
    topic_id = Column(UUID(as_uuid=True), ForeignKey('topics.id'), nullable=False)

    __table_args__ = (
        UniqueConstraint('name', 'topic_id', name='uq_tag_group_name_topic'),
    )
