"""
arxiv_keywords router — reads/writes keywords from scraper_settings.selector_config.

The arxiv_keywords table was removed. Keywords now live in the arxiv scraper
setting's selector_config JSON:
  { "keywords": [...], "categories": [...], "days_back": 1, "max_results": 30 }

Since the REST interface (id, keyword) is still used by the frontend, we use
a base64url encoding of the keyword string as a stable virtual id.

All endpoints accept an optional ?topic_id= query param so that callers can
target the arxiv scraper for a specific topic.
"""
import base64
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.database import get_db
from backend.auth.guards import require_admin

router = APIRouter(prefix="/arxiv-keywords", tags=["arxiv-keywords"])


class ArxivKeywordOut(BaseModel):
    id: str      # base64url(keyword) — stable virtual id
    keyword: str


class ArxivKeywordCreate(BaseModel):
    keyword: str


# ── helpers ───────────────────────────────────────────────────────────────────

def _encode(keyword: str) -> str:
    return base64.urlsafe_b64encode(keyword.encode()).decode().rstrip("=")


def _decode(kid: str) -> str:
    padding = (4 - len(kid) % 4) % 4
    return base64.urlsafe_b64decode(kid + "=" * padding).decode()


def _get_arxiv_setting(db: Session, topic_id: Optional[UUID] = None):
    from models.scraper_setting import ScraperSetting
    q = db.query(ScraperSetting).filter_by(source_type="arxiv", is_active=True)
    if topic_id is not None:
        q = q.filter(ScraperSetting.topic_id == topic_id)
    setting = q.first()
    if not setting:
        raise HTTPException(status_code=404, detail="No active arXiv scraper setting found")
    return setting


def _get_keywords(setting) -> list:
    return list((setting.selector_config or {}).get("keywords") or [])


def _set_keywords(setting, keywords: list, db: Session) -> None:
    cfg = dict(setting.selector_config or {})
    cfg["keywords"] = keywords
    setting.selector_config = cfg
    flag_modified(setting, "selector_config")  # ensure SQLAlchemy tracks JSONB mutation
    db.commit()


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[ArxivKeywordOut])
def list_keywords(
    topic_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    setting = _get_arxiv_setting(db, topic_id)
    return [ArxivKeywordOut(id=_encode(kw), keyword=kw) for kw in _get_keywords(setting)]


@router.post("", response_model=ArxivKeywordOut, status_code=201)
def create_keyword(
    data: ArxivKeywordCreate,
    topic_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    setting = _get_arxiv_setting(db, topic_id)
    keywords = _get_keywords(setting)
    if data.keyword in keywords:
        raise HTTPException(status_code=409, detail="Keyword already exists")
    keywords.append(data.keyword)
    _set_keywords(setting, keywords, db)
    return ArxivKeywordOut(id=_encode(data.keyword), keyword=data.keyword)


@router.delete("/{keyword_id}", status_code=204)
def delete_keyword(
    keyword_id: str,
    topic_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    try:
        keyword = _decode(keyword_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid keyword id")

    setting = _get_arxiv_setting(db, topic_id)
    keywords = _get_keywords(setting)
    if keyword not in keywords:
        raise HTTPException(status_code=404, detail="Keyword not found")
    keywords.remove(keyword)
    _set_keywords(setting, keywords, db)
    return Response(status_code=204)


# ── /arxiv-categories ─────────────────────────────────────────────────────────
# Categories are stored separately in selector_config.categories as plain codes
# (e.g. "cs.SY") and ANDed with keywords in ArxivScraper._build_query().


class ArxivCategoryOut(BaseModel):
    id: str      # base64url(category_code)
    category: str


class ArxivCategoryCreate(BaseModel):
    category: str


_cat_router = APIRouter(prefix="/arxiv-categories", tags=["arxiv-keywords"])


def _get_categories(setting) -> list:
    return list((setting.selector_config or {}).get("categories") or [])


def _set_categories(setting, categories: list, db: Session) -> None:
    cfg = dict(setting.selector_config or {})
    cfg["categories"] = categories
    setting.selector_config = cfg
    flag_modified(setting, "selector_config")
    db.commit()


@_cat_router.get("", response_model=list[ArxivCategoryOut])
def list_categories(
    topic_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    setting = _get_arxiv_setting(db, topic_id)
    return [ArxivCategoryOut(id=_encode(c), category=c) for c in _get_categories(setting)]


@_cat_router.post("", response_model=ArxivCategoryOut, status_code=201)
def create_category(
    data: ArxivCategoryCreate,
    topic_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    setting = _get_arxiv_setting(db, topic_id)
    categories = _get_categories(setting)
    if data.category in categories:
        raise HTTPException(status_code=409, detail="Category already exists")
    categories.append(data.category)
    _set_categories(setting, categories, db)
    return ArxivCategoryOut(id=_encode(data.category), category=data.category)


@_cat_router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: str,
    topic_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    try:
        category = _decode(category_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid category id")

    setting = _get_arxiv_setting(db, topic_id)
    categories = _get_categories(setting)
    if category not in categories:
        raise HTTPException(status_code=404, detail="Category not found")
    categories.remove(category)
    _set_categories(setting, categories, db)
    return Response(status_code=204)


# Export both routers so main.py can include them
cat_router = _cat_router
