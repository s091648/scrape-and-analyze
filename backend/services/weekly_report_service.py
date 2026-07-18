from datetime import date, timedelta
from typing import Dict, Optional, List, TYPE_CHECKING
from uuid import UUID

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from models.weekly_report_translation import WeeklyReportTranslation


def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def get_weekly_report_by_week(db: Session, topic_id: UUID, week_start: date):
    """Return the completed report whose week contains *week_start* (normalized to that week's Monday)."""
    from models.weekly_report import WeeklyReport
    return (
        db.query(WeeklyReport)
        .filter(
            WeeklyReport.topic_id == topic_id,
            WeeklyReport.status == 'completed',
            WeeklyReport.week_start_date == _monday_of_week(week_start),
        )
        .first()
    )


def get_weekly_report_weeks(db: Session, topic_id: UUID) -> List[date]:
    """All week_start_date values with a completed report for *topic_id* — used to grey out
    unavailable weeks in the frontend date picker without fetching full report content."""
    from models.weekly_report import WeeklyReport
    rows = (
        db.query(WeeklyReport.week_start_date)
        .filter(WeeklyReport.topic_id == topic_id, WeeklyReport.status == 'completed')
        .order_by(WeeklyReport.week_start_date.desc())
        .all()
    )
    return [r[0] for r in rows]


def get_weekly_reports(db: Session, topic_id: UUID, limit: int = 20, offset: int = 0):
    from models.weekly_report import WeeklyReport
    query = (
        db.query(WeeklyReport)
        .filter(WeeklyReport.topic_id == topic_id, WeeklyReport.status == 'completed')
        .order_by(WeeklyReport.week_start_date.desc())
    )
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return total, items


def get_latest_weekly_report(db: Session, topic_id: UUID):
    from models.weekly_report import WeeklyReport
    return (
        db.query(WeeklyReport)
        .filter(WeeklyReport.topic_id == topic_id, WeeklyReport.status == 'completed')
        .order_by(WeeklyReport.week_start_date.desc())
        .first()
    )


def get_weekly_report_translations(db: Session, report_ids: List[UUID], lang: str) -> Dict[UUID, "WeeklyReportTranslation"]:
    """Return {weekly_report_id: WeeklyReportTranslation} for the given lang. Empty for English (no-op) or no ids."""
    if lang == "en" or not report_ids:
        return {}
    from models.weekly_report_translation import WeeklyReportTranslation
    rows = (
        db.query(WeeklyReportTranslation)
        .filter(
            WeeklyReportTranslation.weekly_report_id.in_(report_ids),
            WeeklyReportTranslation.language == lang,
        )
        .all()
    )
    return {t.weekly_report_id: t for t in rows}
