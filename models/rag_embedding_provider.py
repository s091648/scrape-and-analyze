from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base


class RagEmbeddingProvider(Base):
    __tablename__ = 'rag_embedding_providers'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role = Column(String(10), nullable=False)
    provider_type = Column(String(20), nullable=False)
    model = Column(String(200), nullable=True)
    endpoint_url = Column(Text, nullable=True)
    api_key_env = Column(String(100), nullable=True)
    dimension = Column(Integer, nullable=False)
    rpm = Column(Integer, nullable=True)
    tpm = Column(Integer, nullable=True)
    rpd = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("role IN ('dense', 'sparse')", name='ck_rag_role'),
        CheckConstraint("provider_type IN ('endpoint', 'local')", name='ck_rag_provider_type'),
        Index(
            'uq_rag_embedding_providers_active_role',
            'role',
            unique=True,
            postgresql_where=Column('is_active') == True,  # noqa: E712
        ),
    )
