from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from models.base import Base


class ArxivKeyword(Base):
    __tablename__ = 'arxiv_keywords'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keyword = Column(String(500), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
