from datetime import date
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.weekly_report import WeeklyReportOut, PaginatedWeeklyReports, WeeklyReportWeeksOut
from backend.services.weekly_report_service import (
    get_weekly_reports,
    get_latest_weekly_report,
    get_weekly_report_by_week,
    get_weekly_report_weeks,
    get_weekly_report_translations,
)

router = APIRouter(prefix="/weekly-reports", tags=["weekly-reports"])


def _to_out(report, translations: dict) -> WeeklyReportOut:
    """Build the response DTO, overriding title/summary_text with the requested-language
    translation when one exists. Falls back to the report's original (English) text otherwise."""
    out = WeeklyReportOut.model_validate(report)
    translation = translations.get(report.id)
    if translation:
        out.title = translation.title
        out.summary_text = translation.summary_text
    return out


@router.get("", response_model=PaginatedWeeklyReports)
def list_weekly_reports(
    topic_id: UUID = Query(...),
    limit: int = Query(default=10, ge=1, le=52),
    offset: int = Query(default=0, ge=0),
    lang: str = Query(default="en"),
    db: Session = Depends(get_db),
):
    total, items = get_weekly_reports(db, topic_id, limit=limit, offset=offset)
    translations = get_weekly_report_translations(db, [r.id for r in items], lang)
    return PaginatedWeeklyReports(
        items=[_to_out(r, translations) for r in items],
        total=total,
        page=offset // limit + 1,
        size=limit,
    )


@router.get("/latest", response_model=Optional[WeeklyReportOut])
def get_latest_report(
    topic_id: UUID = Query(...),
    lang: str = Query(default="en"),
    db: Session = Depends(get_db),
):
    report = get_latest_weekly_report(db, topic_id)
    if not report:
        return None
    translations = get_weekly_report_translations(db, [report.id], lang)
    return _to_out(report, translations)


@router.get("/weeks", response_model=WeeklyReportWeeksOut)
def list_weekly_report_weeks(
    topic_id: UUID = Query(...),
    db: Session = Depends(get_db),
):
    """Lightweight list of week_start_date values with a completed report — drives date-picker availability."""
    return WeeklyReportWeeksOut(weeks=get_weekly_report_weeks(db, topic_id))


@router.get("/by-week", response_model=Optional[WeeklyReportOut])
def get_report_by_week(
    topic_id: UUID = Query(...),
    week_start: date = Query(..., description="Any date within the target week; normalized to that week's Monday"),
    lang: str = Query(default="en"),
    db: Session = Depends(get_db),
):
    report = get_weekly_report_by_week(db, topic_id, week_start)
    if not report:
        return None
    translations = get_weekly_report_translations(db, [report.id], lang)
    return _to_out(report, translations)
