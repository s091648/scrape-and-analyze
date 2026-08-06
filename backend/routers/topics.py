from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from shared.domain.exceptions import NotFoundError
from backend.database import get_db
from backend.auth.guards import require_admin, require_any_token
from backend.schemas.error import error_responses
from backend.schemas.topic import TopicCreate, TopicUpdate, TopicOut

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=list[TopicOut], responses=error_responses(401))
def list_topics(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_any_token),
):
    """Public — returns active topics. Pass ?include_inactive=true for admin views."""
    from models.topic import Topic
    q = db.query(Topic)
    if not include_inactive:
        q = q.filter_by(is_active=True)
    return q.order_by(Topic.sort_order, Topic.created_at).all()


@router.post("", response_model=TopicOut, status_code=201, responses=error_responses(401, 403))
def create_topic(data: TopicCreate, db: Session = Depends(get_db),
                 _=Depends(require_admin)):
    from models.topic import Topic
    obj = Topic(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{topic_id}", response_model=TopicOut, responses=error_responses(401, 403, 404))
def update_topic(topic_id: UUID, data: TopicUpdate, db: Session = Depends(get_db),
                 _=Depends(require_admin)):
    from models.topic import Topic
    obj = db.query(Topic).filter_by(id=topic_id).first()
    if not obj:
        raise NotFoundError("Topic not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{topic_id}", status_code=204, responses=error_responses(401, 403, 404))
def delete_topic(topic_id: UUID, db: Session = Depends(get_db),
                 _=Depends(require_admin)):
    from models.topic import Topic
    obj = db.query(Topic).filter_by(id=topic_id).first()
    if not obj:
        raise NotFoundError("Topic not found")
    obj.is_active = False
    db.commit()
    return Response(status_code=204)
