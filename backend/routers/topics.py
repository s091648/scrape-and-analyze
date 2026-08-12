from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from shared.domain.exceptions import NotFoundError
from shared.cache import CacheGateway, DEFAULT_TTL_SECONDS
from backend.cache import get_cache_gateway
from backend.database import get_db
from backend.auth.guards import require_admin, require_any_token
from backend.schemas.error import error_responses
from backend.schemas.topic import TopicCreate, TopicUpdate, TopicOut

router = APIRouter(prefix="/topics", tags=["topics"])


def _bump_topic_scoped_caches(cache_gateway: CacheGateway) -> None:
    """Topics scope articles/graph/tag_groups reads (research.md — topics has no service
    layer, so this call lives directly in the router, matching this file's style), and the
    topics list is itself cached now too (shared with POST /bootstrap) — bump all four."""
    for namespace in ("articles", "graph", "tag_groups", "topics"):
        cache_gateway.bump_version(namespace)


@router.get("", response_model=list[TopicOut], responses=error_responses(401))
def list_topics(
    response: Response,
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_any_token),
    cache_gateway: CacheGateway = Depends(get_cache_gateway),
):
    """Public — returns active topics. Pass ?include_inactive=true for admin views."""
    def _load():
        from models.topic import Topic
        q = db.query(Topic)
        if not include_inactive:
            q = q.filter_by(is_active=True)
        topics = q.order_by(Topic.sort_order, Topic.created_at).all()
        return [TopicOut.model_validate(t).model_dump(mode="json") for t in topics]

    # Same namespace + params shape as POST /bootstrap's topics fetch (include_inactive=False)
    # — the two endpoints share cache entries and invalidation.
    result = cache_gateway.get_or_set(
        "topics", {"include_inactive": include_inactive}, DEFAULT_TTL_SECONDS, _load,
    )
    response.headers["X-Cache"] = result.status
    return result.value


@router.post("", response_model=TopicOut, status_code=201, responses=error_responses(401, 403))
def create_topic(data: TopicCreate, db: Session = Depends(get_db),
                 _=Depends(require_admin),
                 cache_gateway: CacheGateway = Depends(get_cache_gateway)):
    from models.topic import Topic
    obj = Topic(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    _bump_topic_scoped_caches(cache_gateway)
    return obj


@router.patch("/{topic_id}", response_model=TopicOut, responses=error_responses(401, 403, 404))
def update_topic(topic_id: UUID, data: TopicUpdate, db: Session = Depends(get_db),
                 _=Depends(require_admin),
                 cache_gateway: CacheGateway = Depends(get_cache_gateway)):
    from models.topic import Topic
    obj = db.query(Topic).filter_by(id=topic_id).first()
    if not obj:
        raise NotFoundError("Topic not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    _bump_topic_scoped_caches(cache_gateway)
    return obj


@router.delete("/{topic_id}", status_code=204, responses=error_responses(401, 403, 404))
def delete_topic(topic_id: UUID, db: Session = Depends(get_db),
                 _=Depends(require_admin),
                 cache_gateway: CacheGateway = Depends(get_cache_gateway)):
    from models.topic import Topic
    obj = db.query(Topic).filter_by(id=topic_id).first()
    if not obj:
        raise NotFoundError("Topic not found")
    obj.is_active = False
    db.commit()
    _bump_topic_scoped_caches(cache_gateway)
    return Response(status_code=204)
