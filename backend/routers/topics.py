from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin
from backend.schemas.topic import TopicCreate, TopicUpdate, TopicOut

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=list[TopicOut])
def list_topics(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Public — returns active topics. Pass ?include_inactive=true for admin views."""
    from models.topic import Topic
    q = db.query(Topic)
    if not include_inactive:
        q = q.filter_by(is_active=True)
    return q.order_by(Topic.sort_order, Topic.created_at).all()


@router.post("", response_model=TopicOut, status_code=201)
def create_topic(data: TopicCreate, db: Session = Depends(get_db),
                 _=Depends(require_admin)):
    from models.topic import Topic
    obj = Topic(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{topic_id}", response_model=TopicOut)
def update_topic(topic_id: UUID, data: TopicUpdate, db: Session = Depends(get_db),
                 _=Depends(require_admin)):
    from models.topic import Topic
    obj = db.query(Topic).filter_by(id=topic_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Topic not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{topic_id}", status_code=204)
def delete_topic(topic_id: UUID, db: Session = Depends(get_db),
                 _=Depends(require_admin)):
    from models.topic import Topic
    obj = db.query(Topic).filter_by(id=topic_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Topic not found")
    obj.is_active = False
    db.commit()
    return Response(status_code=204)
