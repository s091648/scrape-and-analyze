from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin
from backend.schemas.llm_provider import LlmProviderCreate, LlmProviderUpdate, LlmProviderOut, LlmProviderReorder

router = APIRouter(prefix="/llm-providers", tags=["llm-providers"])


def _attach_usage(providers, db: Session):
    """Attach usage_24h to each ORM provider instance from analyses table."""
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


def get_providers(db: Session):
    from models.llm_provider import LlmProvider
    providers = db.query(LlmProvider).order_by(LlmProvider.priority).all()
    return _attach_usage(providers, db)


def _check_priority_conflict(db: Session, priority: int, exclude_id: UUID | None = None):
    from models.llm_provider import LlmProvider
    q = db.query(LlmProvider).filter(LlmProvider.priority == priority)
    if exclude_id:
        q = q.filter(LlmProvider.id != exclude_id)
    return q.first()


def create_provider(db: Session, data: LlmProviderCreate):
    from models.llm_provider import LlmProvider
    if _check_priority_conflict(db, data.priority):
        raise HTTPException(status_code=409, detail="Priority already in use by another provider")
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
    if _check_priority_conflict(db, new_priority, exclude_id=provider_id):
        raise HTTPException(status_code=409, detail="Priority already in use by another provider")
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


@router.get("", response_model=list[LlmProviderOut])
def list_providers(db: Session = Depends(get_db), _=Depends(require_admin)):
    return get_providers(db)


@router.post("", response_model=LlmProviderOut, status_code=201)
def create(data: LlmProviderCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    return create_provider(db, data)


@router.put("/reorder", response_model=list[LlmProviderOut])
def reorder(data: LlmProviderReorder, db: Session = Depends(get_db), _=Depends(require_admin)):
    from models.llm_provider import LlmProvider
    priorities = {item.id: item.priority for item in data.order}
    if len(priorities) != len(data.order):
        raise HTTPException(status_code=400, detail="Duplicate provider IDs in reorder request")
    if len(set(priorities.values())) != len(priorities):
        raise HTTPException(status_code=400, detail="Duplicate priority values in reorder request")
    providers = db.query(LlmProvider).filter(LlmProvider.id.in_(priorities.keys())).all()
    if len(providers) != len(priorities):
        raise HTTPException(status_code=404, detail="One or more providers not found")
    conflict = (
        db.query(LlmProvider)
        .filter(
            LlmProvider.id.notin_(priorities.keys()),
            LlmProvider.priority.in_(priorities.values()),
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

        db.refresh(p)
    return _attach_usage(providers, db)


@router.patch("/{provider_id}", response_model=LlmProviderOut)
def update(provider_id: UUID, data: LlmProviderUpdate,
           db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = update_provider(db, provider_id, data)
    if not obj:
        raise HTTPException(status_code=404, detail="Provider not found")
    return obj


@router.delete("/{provider_id}", status_code=204)
def delete(provider_id: UUID, db: Session = Depends(get_db), _=Depends(require_admin)):
    if not delete_provider(db, provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    return Response(status_code=204)