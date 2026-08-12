from datetime import date, timedelta
from typing import Dict, Optional, List, TYPE_CHECKING
from uuid import UUID

from sqlalchemy.orm import Session

from backend.schemas.weekly_report import ArticleSourceOut, WeeklyReportOut

if TYPE_CHECKING:
    from models.weekly_report_translation import WeeklyReportTranslation


def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def resolve_article_sources(report, db: Session) -> List[ArticleSourceOut]:
    """Resolve report.article_ids (ordered) to ArticleSourceOut entries, index-aligned with
    the [N] citation markers in summary_text. Entries that aren't valid UUIDs (pre-existing
    reports generated before article_ids stored real identifiers) are skipped silently."""
    from models.article import Article

    ids: List[UUID] = []
    for raw in (report.article_ids or []):
        try:
            ids.append(UUID(str(raw)))
        except (ValueError, AttributeError, TypeError):
            continue
    if not ids:
        return []

    articles_by_id = {a.id: a for a in db.query(Article).filter(Article.id.in_(ids)).all()}
    sources = []
    for article_id in ids:
        article = articles_by_id.get(article_id)
        if article is None:
            continue
        sources.append(ArticleSourceOut(
            id=article.id,
            title=article.title or "",
            url=article.url,
            public_article_id=article.id,
        ))
    return sources


def to_weekly_report_out(report, translations: dict, db: Session) -> WeeklyReportOut:
    """Build the response DTO, overriding title/summary_text with the requested-language
    translation when one exists. Falls back to the report's original (English) text otherwise."""
    out = WeeklyReportOut.model_validate(report)
    translation = translations.get(report.id)
    if translation:
        out.title = translation.title
        out.summary_text = translation.summary_text
    out.sources = resolve_article_sources(report, db)
    return out


def build_latest_report_payload(db: Session, *, topic_id: UUID, lang: str = "en") -> Optional[dict]:
    """The GET /weekly-reports/latest response body — extracted from routers/weekly_reports.py's
    get_latest_report() so backend/cache_warmup.py (020-redis-caching-layer follow-up) can call
    it directly."""
    report = get_latest_weekly_report(db, topic_id)
    if not report:
        return None
    translations = get_weekly_report_translations(db, [report.id], lang)
    return to_weekly_report_out(report, translations, db).model_dump(mode="json")


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
