from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.schemas.llm_provider import LlmProviderCreate, LlmProviderUpdate


def _attach_usage(providers, db: Session):
    from models.analysis import Analysis
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    rows = (
        db.query(Analysis.model_used, func.count().label("cnt"))
        .filter(Analysis.analyzed_at >= cutoff)
        .group_by(Analysis.model_used)
        .all()
    )
    usage_map = {row.model_used: row.cnt for row in rows}
    for p in providers:
        p.usage_24h = usage_map.get(p.model, 0)
    return providers


def _check_priority_conflict(db: Session, priority: int, provider_type: str, exclude_id: UUID | None = None):
    from models.llm_provider import LlmProvider
    q = db.query(LlmProvider).filter(
        LlmProvider.priority == priority,
        LlmProvider.type == provider_type,
    )
    if exclude_id:
        q = q.filter(LlmProvider.id != exclude_id)
    return q.first()


def get_providers(db: Session):
    from models.llm_provider import LlmProvider
    providers = db.query(LlmProvider).order_by(LlmProvider.priority).all()
    return _attach_usage(providers, db)


def create_provider(db: Session, data: LlmProviderCreate):
    from models.llm_provider import LlmProvider
    if _check_priority_conflict(db, data.priority, data.type):
        raise HTTPException(status_code=409, detail="Priority already in use by another provider of the same type")
    obj = LlmProvider(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    obj.usage_24h = 0
    return obj


def update_provider(db: Session, provider_id: UUID, data: LlmProviderUpdate):
    from models.llm_provider import LlmProvider
    obj = db.query(LlmProvider).filter(LlmProvider.id == provider_id).first()
    if not obj:
        return None
    new_priority = data.priority if data.priority is not None else obj.priority
    new_type = data.type if data.type is not None else obj.type
    if _check_priority_conflict(db, new_priority, new_type, exclude_id=provider_id):
        raise HTTPException(status_code=409, detail="Priority already in use by another provider of the same type")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    obj.usage_24h = 0
    return obj


def delete_provider(db: Session, provider_id: UUID) -> bool:
    from models.llm_provider import LlmProvider
    obj = db.query(LlmProvider).filter(LlmProvider.id == provider_id).first()
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


def reorder_providers(db: Session, priorities: dict[UUID, int]):
    from models.llm_provider import LlmProvider
    if len(set(priorities.values())) != len(priorities):
        raise HTTPException(status_code=400, detail="Duplicate priority values in reorder request")
    providers = db.query(LlmProvider).filter(LlmProvider.id.in_(priorities.keys())).all()
    if len(providers) != len(priorities):
        raise HTTPException(status_code=404, detail="One or more providers not found")
    types_in_batch = {p.type for p in providers}
    conflict = (
        db.query(LlmProvider)
        .filter(
            LlmProvider.id.notin_(priorities.keys()),
            LlmProvider.priority.in_(priorities.values()),
            LlmProvider.type.in_(types_in_batch),
        )
        .first()
    )
    if conflict:
        raise HTTPException(
            status_code=409,
            detail=f"Priority {conflict.priority} is already in use by provider '{conflict.model}' which is not part of this reorder request",
        )
    for p in providers:
        p.priority = priorities[p.id]
    db.commit()
    for p in providers:
        db.refresh(p)
    return _attach_usage(providers, db)
