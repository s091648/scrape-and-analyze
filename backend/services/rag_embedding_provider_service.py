from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.schemas.rag_embedding_provider import RagEmbeddingProviderCreate, RagEmbeddingProviderUpdate


def _check_active_conflict(db: Session, role: str, exclude_id: UUID | None = None):
    """Return existing active provider for role (excluding exclude_id), or None."""
    from models.rag_embedding_provider import RagEmbeddingProvider
    q = db.query(RagEmbeddingProvider).filter(
        RagEmbeddingProvider.role == role,
        RagEmbeddingProvider.is_active.is_(True),
    )
    if exclude_id:
        q = q.filter(RagEmbeddingProvider.id != exclude_id)
    return q.first()


def get_providers(db: Session):
    from models.rag_embedding_provider import RagEmbeddingProvider
    return db.query(RagEmbeddingProvider).order_by(
        RagEmbeddingProvider.role, RagEmbeddingProvider.created_at
    ).all()


def create_provider(db: Session, data: RagEmbeddingProviderCreate):
    from models.rag_embedding_provider import RagEmbeddingProvider
    if data.is_active and _check_active_conflict(db, data.role):
        raise HTTPException(
            status_code=409,
            detail=f"An active {data.role} provider already exists. Deactivate it first.",
        )
    obj = RagEmbeddingProvider(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_provider(db: Session, provider_id: UUID, data: RagEmbeddingProviderUpdate):
    from models.rag_embedding_provider import RagEmbeddingProvider
    obj = db.query(RagEmbeddingProvider).filter(RagEmbeddingProvider.id == provider_id).first()
    if not obj:
        return None
    new_role = data.role if data.role is not None else obj.role
    new_is_active = data.is_active if data.is_active is not None else obj.is_active
    if new_is_active and _check_active_conflict(db, new_role, exclude_id=provider_id):
        raise HTTPException(
            status_code=409,
            detail=f"An active {new_role} provider already exists. Deactivate it first.",
        )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete_provider(db: Session, provider_id: UUID) -> bool:
    from models.rag_embedding_provider import RagEmbeddingProvider
    obj = db.query(RagEmbeddingProvider).filter(RagEmbeddingProvider.id == provider_id).first()
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True
