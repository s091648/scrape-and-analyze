from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from shared.cache import CacheGateway, DEFAULT_TTL_SECONDS
from backend.cache import get_cache_gateway
from backend.database import get_db
from backend.schemas.bootstrap import BootstrapOut
from backend.schemas.topic import TopicOut
from backend.schemas.language import LanguagesResponse
from backend.services.auth_service import (
    compute_guest_id,
    create_guest_access_token,
    GUEST_ACCESS_TOKEN_TTL_SECONDS,
)
from backend.services.language_service import SUPPORTED_LANGUAGES, resolve_language_from_ip

router = APIRouter(tags=["bootstrap"])


@router.post("/bootstrap", response_model=BootstrapOut)
def get_bootstrap(
    request: Request,
    db: Session = Depends(get_db),
    cache_gateway: CacheGateway = Depends(get_cache_gateway),
):
    """Unauthenticated — collapses the SSR-initialization chain (frontend/lib/server/
    ssr-fetch.ts: guest token, then GET /topics + GET /languages, 2 serial round trips
    for a first-time visitor) into one. Always mints a fresh guest access token
    (stateless JWT sign, no DB hit) rather than accepting/validating an existing one —
    a simple, argument-free contract is worth the occasional unused token when the
    caller already held a session or guest credential of its own."""
    guest_id = compute_guest_id(request)

    def _load_topics():
        from models.topic import Topic
        topics = (
            db.query(Topic)
            .filter_by(is_active=True)
            .order_by(Topic.sort_order, Topic.created_at)
            .all()
        )
        return [TopicOut.model_validate(t).model_dump(mode="json") for t in topics]

    # Same namespace + params shape as GET /topics(include_inactive=False) — the two
    # endpoints share cache entries and invalidation (topics.py's _bump_topic_scoped_caches).
    topics_result = cache_gateway.get_or_set(
        "topics", {"include_inactive": False}, DEFAULT_TTL_SECONDS, _load_topics,
    )

    client_ip = request.client.host if request.client else None
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    resolved = resolve_language_from_ip(client_ip) if client_ip else "en"

    return BootstrapOut(
        access_token=create_guest_access_token(guest_id),
        expires_in=GUEST_ACCESS_TOKEN_TTL_SECONDS,
        topics=topics_result.value,
        languages=LanguagesResponse(available=SUPPORTED_LANGUAGES, resolved=resolved),
    )
