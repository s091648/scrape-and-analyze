from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session


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
