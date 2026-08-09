from datetime import date
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from shared.cache import CacheGateway, DEFAULT_TTL_SECONDS
from backend.auth.guards import require_any_token
from backend.cache import get_cache_gateway
from backend.database import get_db
from backend.schemas.error import error_responses
from backend.schemas.weekly_report import ArticleSourceOut, WeeklyReportOut, PaginatedWeeklyReports, WeeklyReportWeeksOut
from backend.services.weekly_report_service import (
    get_weekly_reports,
    get_latest_weekly_report,
    get_weekly_report_by_week,
    get_weekly_report_weeks,
    get_weekly_report_translations,
)

router = APIRouter(prefix="/weekly-reports", tags=["weekly-reports"])


def _resolve_sources(report, db: Session) -> List[ArticleSourceOut]:
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


def _to_out(report, translations: dict, db: Session) -> WeeklyReportOut:
    """Build the response DTO, overriding title/summary_text with the requested-language
    translation when one exists. Falls back to the report's original (English) text otherwise."""
    out = WeeklyReportOut.model_validate(report)
    translation = translations.get(report.id)
    if translation:
        out.title = translation.title
        out.summary_text = translation.summary_text
    out.sources = _resolve_sources(report, db)
    return out


@router.get("", response_model=PaginatedWeeklyReports, responses=error_responses(401))
def list_weekly_reports(
    response: Response,
    topic_id: UUID = Query(...),
    limit: int = Query(default=10, ge=1, le=52),
    offset: int = Query(default=0, ge=0),
    lang: str = Query(default="en"),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_any_token),
    cache_gateway: CacheGateway = Depends(get_cache_gateway),
):
    cache_params = {"topic_id": str(topic_id), "limit": limit, "offset": offset}

    def _load() -> dict:
        total, items = get_weekly_reports(db, topic_id, limit=limit, offset=offset)
        translations = get_weekly_report_translations(db, [r.id for r in items], lang)
        return PaginatedWeeklyReports(
            items=[_to_out(r, translations, db) for r in items],
            total=total,
            page=offset // limit + 1,
            size=limit,
        ).model_dump(mode="json")

    result = cache_gateway.get_or_set("weekly_reports", cache_params, DEFAULT_TTL_SECONDS, _load, lang=lang)
    response.headers["X-Cache"] = result.status
    return result.value


@router.get("/latest", response_model=Optional[WeeklyReportOut], responses=error_responses(401))
def get_latest_report(
    response: Response,
    topic_id: UUID = Query(...),
    lang: str = Query(default="en"),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_any_token),
    cache_gateway: CacheGateway = Depends(get_cache_gateway),
):
    cache_params = {"topic_id": str(topic_id), "op": "latest"}

    def _load() -> Optional[dict]:
        report = get_latest_weekly_report(db, topic_id)
        if not report:
            return None
        translations = get_weekly_report_translations(db, [report.id], lang)
        return _to_out(report, translations, db).model_dump(mode="json")

    result = cache_gateway.get_or_set("weekly_reports", cache_params, DEFAULT_TTL_SECONDS, _load, lang=lang)
    response.headers["X-Cache"] = result.status
    return result.value


@router.get("/weeks", response_model=WeeklyReportWeeksOut, responses=error_responses(401))
def list_weekly_report_weeks(
    response: Response,
    topic_id: UUID = Query(...),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_any_token),
    cache_gateway: CacheGateway = Depends(get_cache_gateway),
):
    """Lightweight list of week_start_date values with a completed report — drives date-picker availability."""
    cache_params = {"topic_id": str(topic_id), "op": "weeks"}

    def _load() -> dict:
        return WeeklyReportWeeksOut(weeks=get_weekly_report_weeks(db, topic_id)).model_dump(mode="json")

    result = cache_gateway.get_or_set("weekly_reports", cache_params, DEFAULT_TTL_SECONDS, _load)
    response.headers["X-Cache"] = result.status
    return result.value


@router.get("/by-week", response_model=Optional[WeeklyReportOut], responses=error_responses(401))
def get_report_by_week(
    response: Response,
    topic_id: UUID = Query(...),
    week_start: date = Query(..., description="Any date within the target week; normalized to that week's Monday"),
    lang: str = Query(default="en"),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_any_token),
    cache_gateway: CacheGateway = Depends(get_cache_gateway),
):
    cache_params = {"topic_id": str(topic_id), "week_start": str(week_start), "op": "by_week"}

    def _load() -> Optional[dict]:
        report = get_weekly_report_by_week(db, topic_id, week_start)
        if not report:
            return None
        translations = get_weekly_report_translations(db, [report.id], lang)
        return _to_out(report, translations, db).model_dump(mode="json")

    result = cache_gateway.get_or_set("weekly_reports", cache_params, DEFAULT_TTL_SECONDS, _load, lang=lang)
    response.headers["X-Cache"] = result.status
    return result.value
