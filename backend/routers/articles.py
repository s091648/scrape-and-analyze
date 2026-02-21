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
