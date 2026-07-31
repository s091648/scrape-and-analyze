from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin
from backend.schemas.error import error_responses
from backend.schemas.monitoring import PaginatedFailedTasks
from backend.services.monitoring_service import get_failed_tasks_paginated

router = APIRouter(tags=["monitoring"])


@router.get("/failed-tasks", response_model=PaginatedFailedTasks, responses=error_responses(401, 403))
def list_failed_tasks(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    total, items = get_failed_tasks_paginated(db, page, size)
    return PaginatedFailedTasks(items=items, total=total, page=page, size=size)
