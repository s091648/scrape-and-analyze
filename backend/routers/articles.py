from typing import Literal, Optional
from uuid import UUID
from datetime import datetime, timezone
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
    published_at: Optional[datetime]
    scraped_at: Optional[datetime]

    class Config:
        from_attributes = True


class PaginatedArticles(BaseModel):
    items: list[ArticleOut]
    total: int
    page: int
    size: int


def get_articles_paginated(db: Session, sort: str, order: str, page: int, size: int):
    from src.models.article import Article
    query = db.query(Article)
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
    db: Session = Depends(get_db),
):
    total, items = get_articles_paginated(db, sort, order, page, size)
    return PaginatedArticles(items=items, total=total, page=page, size=size)


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
    pain_points: Optional[str] = None
    insights: Optional[str] = None
    model_used: Optional[str] = None

    class Config:
        from_attributes = True


def get_article_by_id(db: Session, article_id: UUID):
    from src.models.article import Article
    return db.query(Article).filter(Article.id == article_id).first()


@router.get("/articles/{article_id}", response_model=ArticleDetailOut)
def get_article(article_id: UUID, db: Session = Depends(get_db)):
    article = get_article_by_id(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    analysis = article.analyses[0] if article.analyses else None
    return ArticleDetailOut(
        id=article.id,
        url=article.url,
        source=article.source,
        title=article.title,
        content=article.content,
        published_at=article.published_at,
        scraped_at=article.scraped_at,
        tags=analysis.tags if analysis else [],
        pain_points=analysis.pain_points if analysis else None,
        insights=analysis.insights if analysis else None,
        model_used=analysis.model_used if analysis else None,
    )


@router.get("/failed-tasks", response_model=PaginatedFailedTasks)
def list_failed_tasks(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    from src.models.failed_task import FailedTask
    query = db.query(FailedTask).order_by(FailedTask.failed_at.desc())
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return PaginatedFailedTasks(items=items, total=total, page=page, size=size)
