from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin
from backend.schemas.llm_provider import LlmProviderCreate, LlmProviderUpdate, LlmProviderOut, LlmProviderReorder
from backend.services.llm_provider_service import (
    get_providers,
    create_provider,
    update_provider,
    delete_provider,
    reorder_providers,
)

router = APIRouter(prefix="/llm-providers", tags=["llm-providers"])


@router.get("", response_model=list[LlmProviderOut])
def list_providers(db: Session = Depends(get_db), _=Depends(require_admin)):
    return get_providers(db)


@router.post("", response_model=LlmProviderOut, status_code=201)
def create(data: LlmProviderCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    return create_provider(db, data)


@router.put("/reorder", response_model=list[LlmProviderOut])
def reorder(data: LlmProviderReorder, db: Session = Depends(get_db), _=Depends(require_admin)):
    priorities = {item.id: item.priority for item in data.order}
    if len(priorities) != len(data.order):
        raise HTTPException(status_code=400, detail="Duplicate provider IDs in reorder request")
    return reorder_providers(db, priorities)


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
