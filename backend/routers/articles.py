from typing import Literal, Optional, List
from uuid import UUID
from datetime import datetime, date, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database import get_db

router = APIRouter()

ALLOWED_SORT_COLS = {"scraped_at", "published_at", "source", "title"}


class ArticleOut(BaseModel):
    id: UUID
    url: str
    source: str
    title: str
    content: str
    published_at: Optional[datetime]
    scraped_at: Optional[datetime]

    class Config:
        from_attributes = True


class PaginatedArticles(BaseModel):
    items: list[ArticleOut]
    total: int
    page: int
    size: int


def get_articles_paginated(
    db: Session,
    sort: str,
    order: str,
    page: int,
    size: int,
    sources: List[str] | None = None,
    tags: List[str] | None = None,
    published_after: Optional[date] = None,
    published_before: Optional[date] = None,
    scraped_after: Optional[date] = None,
    scraped_before: Optional[date] = None,
    topic_id: Optional[UUID] = None,
):
    from models.article import Article

    query = db.query(Article)

    if topic_id:
        query = query.filter(Article.topic_id == topic_id)

    if sources:
        query = query.filter(Article.source.in_(sources))

    if tags:
        from models.tag import Tag, article_tags as at
        from sqlalchemy import select
        for tag_name in tags:
            tag_subq = select(at.c.article_id).join(
                Tag, Tag.id == at.c.tag_id
            ).where(Tag.name == tag_name).scalar_subquery()
            query = query.filter(Article.id.in_(tag_subq))

    if published_after:
        query = query.filter(Article.published_at >= published_after)
    if published_before:
        query = query.filter(Article.published_at <= published_before)
    if scraped_after:
        query = query.filter(Article.scraped_at >= scraped_after)
    if scraped_before:
        query = query.filter(Article.scraped_at <= scraped_before)

    col = getattr(Article, sort, None)
    if col is not None:
        query = query.order_by(col.desc() if order == "desc" else col.asc())

    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return total, items


@router.get("/articles", response_model=PaginatedArticles)
def list_articles(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort: Literal["scraped_at", "published_at", "source", "title"] = "scraped_at",
    order: Literal["asc", "desc"] = "desc",
    source: List[str] = Query(default=[]),
    tag: List[str] = Query(default=[]),
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
        tags=tag or None,
        published_after=published_after,
        published_before=published_before,
        scraped_after=scraped_after,
        scraped_before=scraped_before,
        topic_id=topic_id,
    )

    return PaginatedArticles(items=items, total=total, page=page, size=size)


@router.get("/articles/filters/sources")
def get_filter_sources(topic_id: Optional[UUID] = Query(default=None),
                       db: Session = Depends(get_db)):
    from models.article import Article
    query = db.query(Article.source).distinct()
    if topic_id:
        query = query.filter(Article.topic_id == topic_id)
    return [r[0] for r in query.order_by(Article.source).all()]


@router.get("/articles/filters/tags")
def get_filter_tags(topic_id: Optional[UUID] = Query(default=None),
                    db: Session = Depends(get_db)):
    from models.tag import Tag, article_tags as at
    from models.article import Article
    query = db.query(Tag.name).distinct()
    if topic_id:
        query = (
            query
            .join(at, Tag.id == at.c.tag_id)
            .join(Article, Article.id == at.c.article_id)
            .filter(Article.topic_id == topic_id)
        )
    return [r[0] for r in query.order_by(Tag.name).all()]


class TagGroupOut(BaseModel):
    group_name: str
    display_name: str
    color: str
    tags: list[str]


class FailedTaskOut(BaseModel):
    id: UUID
    task_type: str
    article_url: Optional[str]
    exception_type: Optional[str]
    exception_message: Optional[str]
    failed_at: Optional[datetime]
    resolved: bool

    class Config:
        from_attributes = True


class PaginatedFailedTasks(BaseModel):
    items: list[FailedTaskOut]
    total: int
    page: int
    size: int


class ArticleDetailOut(BaseModel):
    id: UUID
    url: str
    source: str
    title: str
    content: str
    published_at: Optional[datetime]
    scraped_at: Optional[datetime]
    tags: list[str] = []
    tag_groups: list[TagGroupOut] = []
    pain_points: Optional[str] = None
    insights: Optional[str] = None
    innovations: Optional[str] = None
    model_used: Optional[str] = None

    class Config:
        from_attributes = True


def get_article_by_id(db: Session, article_id: UUID):
    from models.article import Article
    return db.query(Article).filter(Article.id == article_id).first()


def get_tag_groups_for_article(db: Session, article_id: UUID, lang: str = "en") -> list:
    from models.tag import Tag, article_tags as at
    from models.tag_translation import TagTranslation
    from models.tag_group_translation import TagGroupTranslation

    tags = (
        db.query(Tag)
        .join(at, Tag.id == at.c.tag_id)
        .filter(at.c.article_id == article_id)
        .order_by(Tag.tag_group_name, Tag.name)
        .all()
    )

    # Batch-load translations for tags and groups
    tag_ids = [t.id for t in tags]
    tag_trans_map = {}
    group_trans_map = {}
    if lang != "en" and tag_ids:
        tag_translations = db.query(TagTranslation).filter(
            TagTranslation.tag_id.in_(tag_ids),
            TagTranslation.language == lang,
        ).all()
        tag_trans_map = {tt.tag_id: tt.name for tt in tag_translations}

        group_ids = list({t.group_def.id for t in tags if t.group_def})
        if group_ids:
            group_translations = db.query(TagGroupTranslation).filter(
                TagGroupTranslation.tag_group_definition_id.in_(group_ids),
                TagGroupTranslation.language == lang,
            ).all()
            group_trans_map = {gt.tag_group_definition_id: gt.display_name for gt in group_translations}

    groups: dict = {}
    for tag in tags:
        gname = tag.tag_group_name
        if gname not in groups:
            gdef = tag.group_def
            display_name = gname
            if gdef:
                if lang != "en" and gdef.id in group_trans_map:
                    display_name = group_trans_map[gdef.id]
                else:
                    display_name = gdef.display_name
            groups[gname] = {
                "group_name": gname,
                "display_name": display_name,
                "color": gdef.color_hex if gdef else "#6b7280",
                "tags": [],
            }
        tag_name = tag_trans_map.get(tag.id, tag.name) if lang != "en" else tag.name
        groups[gname]["tags"].append(tag_name)
    return list(groups.values())


@router.get("/articles/{article_id}", response_model=ArticleDetailOut)
def get_article(article_id: UUID, lang: str = Query(default="en"), db: Session = Depends(get_db)):
    from models.tag import Tag, article_tags as at
    from models.analysis_translation import AnalysisTranslation
    article = get_article_by_id(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    analysis = article.analyses[0] if article.analyses else None
    tag_names = (
        db.query(Tag.name)
        .join(at, Tag.id == at.c.tag_id)
        .filter(at.c.article_id == article_id)
        .order_by(Tag.name)
        .all()
    )

    # Get content from analysis_translations (all languages including English)
    pain_points = None
    insights = None
    innovations = None
    if analysis:
        translation = db.query(AnalysisTranslation).filter(
            AnalysisTranslation.analysis_id == analysis.id,
            AnalysisTranslation.language == lang
        ).first()
        if not translation and lang != "en":
            # Fallback to English if requested language not available
            translation = db.query(AnalysisTranslation).filter(
                AnalysisTranslation.analysis_id == analysis.id,
                AnalysisTranslation.language == "en"
            ).first()
        if translation:
            pain_points = translation.pain_points
            insights = translation.insights
            innovations = translation.innovations

    # Build tag_groups first (which also handles per-tag translation),
    # then derive flat tags list from it for consistency.
    tag_groups_data = get_tag_groups_for_article(db, article_id, lang=lang)
    flat_tags = []
    for grp in tag_groups_data:
        flat_tags.extend(grp["tags"])

    return ArticleDetailOut(
        id=article.id,
        url=article.url,
        source=article.source,
        title=article.title,
        content=article.content,
        published_at=article.published_at,
        scraped_at=article.scraped_at,
        tags=flat_tags,
        tag_groups=tag_groups_data,
        pain_points=pain_points,
        insights=insights,
        innovations=innovations,
        model_used=analysis.model_used if analysis else None,
    )


@router.get("/failed-tasks", response_model=PaginatedFailedTasks)
def list_failed_tasks(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    from models.failed_task import FailedTask
    query = db.query(FailedTask).order_by(FailedTask.failed_at.desc())
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return PaginatedFailedTasks(items=items, total=total, page=page, size=size)
