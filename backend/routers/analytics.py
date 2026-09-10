from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin
from backend.schemas.error import error_responses
from backend.schemas.analytics import AnalyticsOverview
from backend.services.article_service import get_analytics_overview

router = APIRouter(prefix="/admin/analytics", tags=["analytics"])

# Matches the frontend's window selector. Anything else is clamped to the default rather than
# 422'd — the page can only send these three, so a stray value is a bug not worth surfacing.
ALLOWED_DAYS = (7, 30, 90)
DEFAULT_DAYS = 30


@router.get("/overview", response_model=AnalyticsOverview, responses=error_responses(401, 403))
def analytics_overview(
    days: int = Query(DEFAULT_DAYS),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    if days not in ALLOWED_DAYS:
        days = DEFAULT_DAYS
    return get_analytics_overview(db, days)
