from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin
from backend.schemas.llm_provider import LlmProviderCreate, LlmProviderUpdate, LlmProviderOut

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


def create_provider(db: Session, data: LlmProviderCreate):
    from models.llm_provider import LlmProvider
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