from typing import Literal, Optional, List
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.article import ArticleOut, PaginatedArticles, ArticleDetailOut
from backend.services.article_service import (
    get_articles_paginated,
    build_article_out,
    get_article_by_id,
    get_tag_groups_for_article,
    get_filter_sources,
    get_filter_original_sources,
    get_filter_tags,
)

router = APIRouter()


@router.get("/articles", response_model=PaginatedArticles)
def list_articles(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort: Literal["scraped_at", "published_at", "source", "title"] = "scraped_at",
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
    lang: str = Query(default="en"),
    db: Session = Depends(get_db),
):
    total, items = get_articles_paginated(
        db, sort, order, page, size,
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
    )
    return PaginatedArticles(
        items=[build_article_out(item) for item in items],
        total=total,
        page=page,
        size=size,
    )


@router.get("/source-categories")
def get_source_categories():
    from backend.constants import SOURCE_CATEGORIES
    return {k: [{"value": e.value, "label": e.label} for e in v] for k, v in SOURCE_CATEGORIES.items()}


@router.get("/articles/filters/sources")
def list_filter_sources(
    topic_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
):
    return get_filter_sources(db, topic_id)


@router.get("/articles/filters/original-sources")
def list_filter_original_sources(
    topic_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
):
    return get_filter_original_sources(db, topic_id)


@router.get("/articles/filters/tags")
def list_filter_tags(
    topic_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
):
    return get_filter_tags(db, topic_id)


@router.get("/articles/{article_id}", response_model=ArticleDetailOut)
def get_article(
    article_id: UUID,
    lang: str = Query(default="en"),
    db: Session = Depends(get_db),
):
    article = get_article_by_id(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

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
    )
