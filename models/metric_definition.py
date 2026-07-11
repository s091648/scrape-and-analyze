from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from models.base import Base


class MetricDefinition(Base):
    __tablename__ = 'metric_definitions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_key = Column(String(50), nullable=False)
    provider_name = Column(String(50), nullable=False)
    priority = Column(Integer, nullable=False)
    extractor_type = Column(String(20), nullable=False)
    extractor_spec = Column(JSONB, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    label_i18n_key = Column(String(100), nullable=False)
    format_hint = Column(String(20), nullable=True)
    unit = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint('metric_key', 'provider_name', name='uq_metric_definitions_metric_key_provider_name'),
        CheckConstraint("extractor_type IN ('json_path', 'code')", name='ck_metric_definitions_extractor_type'),
    )
