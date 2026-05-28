from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Integer, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base


class LlmProvider(Base):
    __tablename__ = 'llm_providers'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False, unique=True)
    api_key_env = Column(String(100), nullable=False)
    priority = Column(Integer, nullable=False)
    type = Column(String(20), nullable=False, default='llm')
    type = Column(String(20), nullable=False, default='llm')
    is_active = Column(Boolean, nullable=False, default=True)
    rpm = Column(Integer, nullable=True)
    tpm = Column(Integer, nullable=True)
    rpd = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
