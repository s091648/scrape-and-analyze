from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin
from backend.schemas.error import error_responses
from backend.schemas.monitoring import PaginatedFailedTasks, QueryTextOut, QueryTextsResponse
from backend.services.monitoring_service import get_failed_tasks_paginated, get_query_texts

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


@router.get("/db/query-texts", response_model=QueryTextsResponse, responses=error_responses(401, 403))
def list_query_texts(
    queryid: list[int] = Query(..., min_length=1, max_length=50,
                               description="pg_stat_statements query ids (repeat the param per id)"),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Resolve the `queryid` label on the monitoring dashboard's pg_stat_statements
    metrics (Database app) to the statement text."""
    available, rows = get_query_texts(db, queryid)
    return QueryTextsResponse(
        available=available,
        items=[QueryTextOut(queryid=str(qid), query=query) for qid, query in rows],
    )
