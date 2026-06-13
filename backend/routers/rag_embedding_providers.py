from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin
from backend.schemas.rag_embedding_provider import (
    RagEmbeddingProviderCreate,
    RagEmbeddingProviderUpdate,
    RagEmbeddingProviderOut,
)
from backend.services.rag_embedding_provider_service import (
    get_providers,
    create_provider,
    update_provider,
    delete_provider,
)

router = APIRouter(prefix="/rag-embedding-providers", tags=["rag-embedding-providers"])


@router.get("", response_model=list[RagEmbeddingProviderOut])
def list_providers(db: Session = Depends(get_db), _=Depends(require_admin)):
    return get_providers(db)


@router.post("", response_model=RagEmbeddingProviderOut, status_code=201)
def create(data: RagEmbeddingProviderCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    return create_provider(db, data)


@router.patch("/{provider_id}", response_model=RagEmbeddingProviderOut)
def update(provider_id: UUID, data: RagEmbeddingProviderUpdate,
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
