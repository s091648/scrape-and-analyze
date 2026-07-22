import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base
from models.db_schema import DbSchema


class Topic(Base):
    __tablename__ = "topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200), nullable=False)
    description = Column(Text)
    color_hex = Column(String(7))
    prompt_override = Column(Text)
    sort_order = Column(Integer)
    is_active = Column(Boolean, nullable=False, default=True)
    tag_mode = Column(String(20), nullable=False, default='unsupervised')
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_topics_name", "name"),
        {'schema': DbSchema.CORE.value},
    )
