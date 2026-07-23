from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.shared.domain.exceptions import NotFoundError
from backend.database import get_db
from backend.auth.guards import require_admin
from backend.schemas.error import error_responses
from backend.schemas.metric_definition import (
    MetricDefinitionDisplayOut,
    MetricDefinitionAdminOut,
    MetricDefinitionAdminUpdate,
)
from backend.services.metric_definition_service import (
    get_enabled_metric_display,
    get_all_metric_definitions,
    update_metric_definition,
)

router = APIRouter(tags=["metric-definitions"])


@router.get("/metric-definitions", response_model=list[MetricDefinitionDisplayOut])
def list_enabled_metric_definitions(db: Session = Depends(get_db)):
    """Public — display metadata for enabled catalog metrics only (FR-037)."""
    return get_enabled_metric_display(db)


@router.get("/admin/metric-definitions", response_model=list[MetricDefinitionAdminOut], responses=error_responses(401, 403))
def list_all_metric_definitions(db: Session = Depends(get_db), _=Depends(require_admin)):
    return get_all_metric_definitions(db)


@router.patch("/admin/metric-definitions/{definition_id}", response_model=MetricDefinitionAdminOut, responses=error_responses(401, 403, 404))
def patch_metric_definition(
    definition_id: UUID,
    data: MetricDefinitionAdminUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    obj = update_metric_definition(db, definition_id, enabled=data.enabled, icon_name=data.icon_name)
    if not obj:
        raise NotFoundError("Metric definition not found")
    return obj
