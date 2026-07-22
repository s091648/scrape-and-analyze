from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator

# Mirrors frontend/components/features/articles/metric-icons.ts's METRIC_ICON_NAMES —
# keep in sync. The backend rejects any icon_name outside this set so an admin can never
# set a value the frontend has no component for (FR-041).
ICON_WHITELIST = {
    "quote", "eye", "trending-up", "award", "star", "bar-chart", "users", "thumbs-up",
    "download", "share-2", "bookmark", "heart", "message-square", "flame", "trophy",
    "hash", "percent", "clock", "book-open", "network",
}


class MetricDefinitionDisplayOut(BaseModel):
    """Public shape — display metadata only, no extraction/provider internals (FR-037)."""
    metric_key: str
    label_i18n_key: str
    icon_name: Optional[str] = None
    format_hint: Optional[str] = None
    unit: Optional[str] = None


class MetricDefinitionAdminOut(BaseModel):
    """Admin shape — one row per metric_key (not per provider); provider/priority extraction
    config is intentionally not exposed here, it's a maintainer-only implementation detail."""
    id: UUID
    metric_key: str
    label_i18n_key: str
    icon_name: Optional[str] = None
    format_hint: Optional[str] = None
    unit: Optional[str] = None
    enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MetricDefinitionAdminUpdate(BaseModel):
    """The only admin-editable fields (FR-041) — extraction config (metric_providers) and
    label_i18n_key remain maintainer-only via migration."""
    enabled: Optional[bool] = None
    icon_name: Optional[str] = None

    @field_validator("icon_name")
    @classmethod
    def validate_icon_name(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in ICON_WHITELIST:
            raise ValueError(f"icon_name must be one of {sorted(ICON_WHITELIST)}")
        return value
