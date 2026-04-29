"""scraper_keywords router — unified keyword/category management for all scraper types.

All keywords live in the scraper_keywords table, discriminated by keyword_type:
  rss            – regex patterns used to filter RSS feed entries
  arxiv_keyword  – arXiv API query strings, e.g. ti:"digital twin"
  arxiv_category – arXiv subject category codes, e.g. cs.GR

All endpoints are scoped by topic_id.  The keyword_type query param selects the
variant; omitting it returns all types for the topic.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin
from src.modules.collection.domain.value_objects import VALID_KEYWORD_TYPES

router = APIRouter(prefix="/scraper-keywords", tags=["scraper-keywords"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ScraperKeywordOut(BaseModel):
    id: str
    keyword_type: str
    keyword: str


class ScraperKeywordCreate(BaseModel):
    keyword: str
    keyword_type: str = "rss"

    @field_validator("keyword_type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in VALID_KEYWORD_TYPES:
            raise ValueError(f"keyword_type must be one of {sorted(VALID_KEYWORD_TYPES)}")
        return v


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[ScraperKeywordOut])
def list_keywords(
    topic_id: UUID = Query(...),
    keyword_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    from models.scraper_keyword import ScraperKeyword
    q = db.query(ScraperKeyword).filter_by(topic_id=topic_id)
    if keyword_type is not None:
        q = q.filter_by(keyword_type=keyword_type)
    rows = q.order_by(ScraperKeyword.created_at).all()
    return [ScraperKeywordOut(id=str(r.id), keyword_type=r.keyword_type, keyword=r.keyword) for r in rows]


@router.post("", response_model=ScraperKeywordOut, status_code=201)
def create_keyword(
    data: ScraperKeywordCreate,
    topic_id: UUID = Query(...),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    from models.scraper_keyword import ScraperKeyword
    if db.query(ScraperKeyword).filter_by(
        topic_id=topic_id, keyword_type=data.keyword_type, keyword=data.keyword
    ).first():
        raise HTTPException(status_code=409, detail="Keyword already exists")
    row = ScraperKeyword(topic_id=topic_id, keyword_type=data.keyword_type, keyword=data.keyword)
    db.add(row)
    db.commit()
    db.refresh(row)
    return ScraperKeywordOut(id=str(row.id), keyword_type=row.keyword_type, keyword=row.keyword)


@router.delete("/{keyword_id}", status_code=204)
def delete_keyword(
    keyword_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    from models.scraper_keyword import ScraperKeyword
    row = db.query(ScraperKeyword).filter_by(id=keyword_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Keyword not found")
    db.delete(row)
    db.commit()
    return Response(status_code=204)
