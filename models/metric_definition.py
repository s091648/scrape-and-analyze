from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base


class MetricDefinition(Base):
    """One row per metric_key — display/user-facing config. `icon_name` and `enabled` are
    admin-editable (FR-041); everything else here, and all of `MetricProvider`, is
    maintainer-only via migration (FR-022). See metric_providers for extraction config."""
    __tablename__ = 'metric_definitions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_key = Column(String(50), nullable=False)
    label_i18n_key = Column(String(100), nullable=False)
    format_hint = Column(String(20), nullable=True)
    unit = Column(String(20), nullable=True)
    icon_name = Column(String(50), nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint('metric_key', name='uq_metric_definitions_metric_key'),
    )
