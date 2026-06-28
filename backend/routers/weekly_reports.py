from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.weekly_report import WeeklyReportOut, PaginatedWeeklyReports
from backend.services.weekly_report_service import get_weekly_reports, get_latest_weekly_report

router = APIRouter(prefix="/weekly-reports", tags=["weekly-reports"])


@router.get("", response_model=PaginatedWeeklyReports)
def list_weekly_reports(
    topic_id: UUID = Query(...),
    limit: int = Query(default=10, ge=1, le=52),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    total, items = get_weekly_reports(db, topic_id, limit=limit, offset=offset)
    return PaginatedWeeklyReports(
        items=[WeeklyReportOut.model_validate(r) for r in items],
        total=total,
        page=offset // limit + 1,
        size=limit,
    )


@router.get("/latest", response_model=Optional[WeeklyReportOut])
def get_latest_report(
    topic_id: UUID = Query(...),
    db: Session = Depends(get_db),
):
    report = get_latest_weekly_report(db, topic_id)
    if not report:
        return None
    return WeeklyReportOut.model_validate(report)
