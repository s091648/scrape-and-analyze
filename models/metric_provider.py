from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from models.base import Base
from models.db_schema import DbSchema


class MetricProvider(Base):
    """Maintainer-only extraction config: which external source(s) can supply a value for a
    metric_key, and how. A metric_key MAY have more than one provider row (see
    metric_definitions.py docstring / alembic 23 for why) — never admin-editable (FR-022)."""
    __tablename__ = 'metric_providers'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_definition_id = Column(UUID(as_uuid=True), ForeignKey('ai_infra.metric_definitions.id', ondelete='CASCADE'), nullable=False)
    provider_name = Column(String(50), nullable=False)
    priority = Column(Integer, nullable=False)
    extractor_type = Column(String(20), nullable=False)
    extractor_spec = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint('metric_definition_id', 'provider_name', name='uq_metric_providers_definition_provider'),
        CheckConstraint("extractor_type IN ('json_path', 'code')", name='ck_metric_providers_extractor_type'),
        {'schema': DbSchema.AI_INFRA.value},
    )
