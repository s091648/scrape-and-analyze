from typing import Literal, Optional, List
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from shared.domain.exceptions import NotFoundError
from shared.cache import CacheGateway, DEFAULT_TTL_SECONDS
from backend.config import REDIS_URL
from backend.cache import get_cache_gateway
from backend.database import get_db
from backend.schemas.error import error_responses
from backend.schemas.article import ArticleOut, PaginatedArticles, ArticleDetailOut
from backend.services.article_service import (
    build_articles_list_payload,
    get_article_by_id,
    get_tag_groups_for_article,
    get_filter_sources,
    get_filter_original_sources,
    get_filter_tags,
    flush_view_counts,
)
from backend.auth.guards import get_optional_user_id, require_admin, require_any_token

router = APIRouter(tags=["articles"])


def _get_redis():
    import redis.asyncio as aioredis
    return aioredis.from_url(REDIS_URL)


@router.get("/articles", response_model=PaginatedArticles, responses=error_responses(401))
def list_articles(
    response: Response,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    # 2026-07-12: no longer a fixed Literal — any deployment-defined catalog metric_key is a
    # valid sort value in addition to the fixed fields and view_count; see article_service.py.
    sort: str = Query(default="scraped_at"),
    order: Literal["asc", "desc"] = "desc",
    source: List[str] = Query(default=[]),
    aggregator: List[str] = Query(default=[]),
    original_source: List[str] = Query(default=[]),
    tag: List[str] = Query(default=[]),
    tag_id: List[UUID] = Query(default=[]),
    tag_group: List[str] = Query(default=[]),
    published_after: Optional[date] = Query(default=None),
    published_before: Optional[date] = Query(default=None),
    scraped_after: Optional[date] = Query(default=None),
    scraped_before: Optional[date] = Query(default=None),
    topic_id: Optional[UUID] = Query(default=None),
    favorites_only: bool = Query(default=False),
    lang: str = Query(default="en"),
    db: Session = Depends(get_db),
    current_user_id: Optional[UUID] = Depends(get_optional_user_id),
    _token: dict = Depends(require_any_token),
    cache_gateway: CacheGateway = Depends(get_cache_gateway),
):
    # user_id/favorites_only are included in the cache key (not just filters) because the
    # response embeds per-user state (is_favorited) — without this, one user's cached
    # response could leak their favorite-star state to another user (research.md/data-model.md
    # only cover the filter-key shape; this personalization nuance is an implementation detail).
    cache_params = {
        "page": page, "size": size, "sort": sort, "order": order,
        "source": sorted(source), "aggregator": sorted(aggregator),
        "original_source": sorted(original_source), "tag": sorted(tag),
        "tag_id": sorted(str(t) for t in tag_id), "tag_group": sorted(tag_group),
        "published_after": str(published_after), "published_before": str(published_before),
        "scraped_after": str(scraped_after), "scraped_before": str(scraped_before),
        "topic_id": str(topic_id), "favorites_only": favorites_only,
        "user_id": str(current_user_id),
    }

    def _load() -> dict:
        return build_articles_list_payload(
            db, sort=sort, order=order, page=page, size=size,
            sources=source or None,
            aggregators=aggregator or None,
            original_sources=original_source or None,
            tags=tag or None,
            tag_ids=tag_id or None,
            tag_groups=tag_group or None,
            published_after=published_after,
            published_before=published_before,
            scraped_after=scraped_after,
            scraped_before=scraped_before,
            topic_id=topic_id,
            user_id=current_user_id,
            favorites_only=favorites_only,
            lang=lang,
        )

    result = cache_gateway.get_or_set("articles", cache_params, DEFAULT_TTL_SECONDS, _load, lang=lang)
    response.headers["X-Cache"] = result.status
    return result.value


@router.get("/source-categories", responses=error_responses(401))
def get_source_categories(_token: dict = Depends(require_any_token)):
    from backend.constants import SOURCE_CATEGORIES
    return {k: [{"value": e.value, "label": e.label} for e in v] for k, v in SOURCE_CATEGORIES.items()}


@router.get("/articles/filters/sources", responses=error_responses(401))
def list_filter_sources(
    topic_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_any_token),
):
    return get_filter_sources(db, topic_id)


@router.get("/articles/filters/original-sources", responses=error_responses(401))
def list_filter_original_sources(
    topic_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_any_token),
):
    return get_filter_original_sources(db, topic_id)


@router.get("/articles/filters/tags", responses=error_responses(401))
def list_filter_tags(
    topic_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_any_token),
):
    return get_filter_tags(db, topic_id)


@router.get("/articles/{article_id}", response_model=ArticleDetailOut, responses=error_responses(401, 404))
def get_article(
    article_id: UUID,
    response: Response,
    lang: str = Query(default="en"),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_any_token),
    cache_gateway: CacheGateway = Depends(get_cache_gateway),
):
    # Only the static shape (content/tags/translations/analysis) is cached — metrics/
    # view_count are updated out-of-band by refresh_metrics.py's cron and the 15-min
    # view-count flush (backend/main.py _periodic_view_flush), neither of which bumps
    # this cache namespace, so they're always queried fresh below instead of being cached
    # stale for up to a full TTL window (research.md — static/dynamic split, not a
    # freshness-based TTL: article content itself only changes via writes that already
    # call bump_version("articles")).
    cache_params = {"article_id": str(article_id), "op": "detail"}

    def _load() -> dict:
        article = get_article_by_id(db, article_id)
        if not article:
            raise NotFoundError("Article not found")

        analysis = article.analyses[0] if article.analyses else None
        pain_points = insights = innovations = None
        if analysis:
            from models.analyses_translation import AnalysesTranslation
            translation = db.query(AnalysesTranslation).filter(
                AnalysesTranslation.analysis_id == analysis.id,
                AnalysesTranslation.language == lang,
            ).first()
            if not translation and lang != "en":
                translation = db.query(AnalysesTranslation).filter(
                    AnalysesTranslation.analysis_id == analysis.id,
                    AnalysesTranslation.language == "en",
                ).first()
            if translation:
                pain_points = translation.pain_points
                insights = translation.insights
                innovations = translation.innovations

        tag_groups_data = get_tag_groups_for_article(db, article_id, lang=lang)
        flat_tags = [t for grp in tag_groups_data for t in grp["tags"]]

        translated_title = None
        translated_content = None
        if lang != "en":
            from models.article_translation import ArticleTranslation
            body_translation = db.query(ArticleTranslation).filter(
                ArticleTranslation.article_id == article_id,
                ArticleTranslation.language == lang,
            ).first()
            if body_translation:
                translated_title = body_translation.title
                translated_content = body_translation.content

        meta = article.metadata_ or {}
        return ArticleDetailOut(
            id=article.id,
            url=article.url,
            source=article.source,
            title=article.title,
            content=article.content,
            published_at=article.published_at,
            scraped_at=article.scraped_at,
            via_source=meta.get("via_source"),
            original_source=article.original_source or meta.get("original_source"),
            tags=flat_tags,
            tag_groups=tag_groups_data,
            pain_points=pain_points,
            insights=insights,
            innovations=innovations,
            model_used=analysis.model_used if analysis else None,
            translated_title=translated_title,
            translated_content=translated_content,
            has_vectors=article.has_vectors,
            metrics={},
            view_count=0,
        ).model_dump(mode="json")

    cache_result = cache_gateway.get_or_set("articles", cache_params, DEFAULT_TTL_SECONDS, _load, lang=lang)
    response.headers["X-Cache"] = cache_result.status
    result = cache_result.value

    from models.article_metrics import ArticleMetrics as ArticleMetricsModel
    from models.article_metric_value import ArticleMetricValue
    metrics = db.query(ArticleMetricsModel).filter(ArticleMetricsModel.article_id == article_id).first()
    metric_rows = db.query(ArticleMetricValue).filter(
        ArticleMetricValue.article_id == article_id,
        ArticleMetricValue.value.isnot(None),
    ).all()
    result["metrics"] = {mv.metric_key: float(mv.value) for mv in metric_rows}
    result["view_count"] = metrics.view_count if metrics else 0
    return result


@router.post("/articles/{article_id}/view", status_code=204, responses=error_responses(401))
async def record_article_view(article_id: UUID, request: Request, _token: dict = Depends(require_any_token)):
    """Increment view count in Redis with IP deduplication (24h TTL)."""
    client_ip = request.client.host if request.client else "unknown"
    dedup_key = f"viewed:{client_ip}:{article_id}"
    view_key = f"view:{article_id}"
    r = _get_redis()
    try:
        already_viewed = await r.get(dedup_key)
        if not already_viewed:
            await r.incr(view_key)
            await r.set(dedup_key, "1", ex=86400)
    finally:
        await r.aclose()
    return Response(status_code=204)


@router.post("/admin/articles/flush-view-counts", responses=error_responses(401, 403))
async def admin_flush_view_counts(db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    """Flush Redis view counts into article_metrics table."""
    flushed = await flush_view_counts(db)
    return {"flushed": flushed}
