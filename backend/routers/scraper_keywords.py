from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from shared.domain.exceptions import NotFoundError
from backend.database import get_db
from backend.auth.guards import require_admin
from backend.schemas.error import error_responses
from backend.schemas.scraper_keyword import ScraperKeywordOut, ScraperKeywordCreate
from backend.services.scraper_keyword_service import list_keywords, create_keyword, delete_keyword

router = APIRouter(prefix="/scraper-keywords", tags=["scraper-keywords"])


@router.get("", response_model=List[ScraperKeywordOut], responses=error_responses(401, 403))
def list_keywords_endpoint(
    topic_id: UUID = Query(...),
    keyword_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    rows = list_keywords(db, topic_id, keyword_type)
    return [ScraperKeywordOut(id=str(r.id), keyword_type=r.keyword_type, keyword=r.keyword) for r in rows]


@router.post("", response_model=ScraperKeywordOut, status_code=201, responses=error_responses(401, 403))
def create_keyword_endpoint(
    data: ScraperKeywordCreate,
    topic_id: UUID = Query(...),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    row = create_keyword(db, topic_id, data.keyword_type, data.keyword)
    return ScraperKeywordOut(id=str(row.id), keyword_type=row.keyword_type, keyword=row.keyword)


@router.delete("/{keyword_id}", status_code=204, responses=error_responses(401, 403, 404))
def delete_keyword_endpoint(
    keyword_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    if not delete_keyword(db, keyword_id):
        raise NotFoundError("Keyword not found")
    return Response(status_code=204)
