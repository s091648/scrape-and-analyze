from datetime import date
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from shared.domain.exceptions import ValidationError
from backend.database import get_db
from backend.schemas.error import error_responses
from backend.schemas.article import PaginatedArticles
from backend.schemas.search import AutocompleteResponse
from backend.services.search_service import search_articles_hybrid, suggest_terms
from backend.auth.guards import require_any_token

router = APIRouter(tags=["search"])


@router.get("/search", response_model=PaginatedArticles, responses=error_responses(400, 401))
async def search(
    q: str = Query(...),
    topic_id: Optional[UUID] = Query(default=None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    exact_match_only: bool = Query(
        False,
        description="Drop non-exact-match candidates before total/pagination are computed "
                     "(default off). Backs the frontend's 'exact matches only' checkbox — "
                     "must be applied server-side, not as a per-page client filter, or "
                     "total/page count would disagree with what's actually shown.",
    ),
    # Same names/semantics as GET /articles' own filter params (backend/routers/articles.py)
    # — narrow the candidate pool before ranking/pagination, see search_articles_hybrid's
    # own docstring for why that must happen server-side rather than as a page-level filter.
    aggregator: List[str] = Query(default=[]),
    original_source: List[str] = Query(default=[]),
    tag: List[str] = Query(default=[]),
    tag_group: List[str] = Query(default=[]),
    published_after: Optional[date] = Query(default=None),
    published_before: Optional[date] = Query(default=None),
    scraped_after: Optional[date] = Query(default=None),
    scraped_before: Optional[date] = Query(default=None),
    sort: Optional[str] = Query(
        default=None,
        description="Overrides the default ordering (RRF relevance for hybrid search, "
                     "newest-first for exact_match_only) with one of published_at/"
                     "scraped_at/source/title. Omit to keep the default ordering.",
    ),
    order: str = Query(default="desc"),
    lang: str = Query(default="en"),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_any_token),
):
    query = q.strip()
    if not query:
        raise ValidationError("q must not be empty")
    return await search_articles_hybrid(
        db, query=query, topic_id=topic_id, page=page, size=size,
        exact_match_only=exact_match_only, lang=lang,
        aggregators=aggregator or None, original_sources=original_source or None,
        tags=tag or None, tag_groups=tag_group or None,
        published_after=published_after, published_before=published_before,
        scraped_after=scraped_after, scraped_before=scraped_before,
        sort=sort, order=order,
    )


@router.get("/search/autocomplete", response_model=AutocompleteResponse, responses=error_responses(400, 401))
def autocomplete(
    prefix: str = Query(...),
    topic_id: Optional[UUID] = Query(default=None),
    lang: str = Query(default="en"),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_any_token),
):
    typed = prefix.strip()
    if not typed:
        raise ValidationError("prefix must not be empty")
    return suggest_terms(db, topic_id=topic_id, prefix=typed, lang=lang)
