from sqlalchemy import Column, String, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from src.models.article import Base
import uuid


class TagGroupDefinition(Base):
    __tablename__ = 'tag_group_definitions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text)
    color_hex = Column(String(7))
    sort_order = Column(Integer)
