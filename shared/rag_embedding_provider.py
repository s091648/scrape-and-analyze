from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def load_active_rag_providers(session: "Session") -> list:
    """Return active RagEmbeddingProvider ORM rows (dense first, then sparse)."""
    from models.rag_embedding_provider import RagEmbeddingProvider
    return (
        session.query(RagEmbeddingProvider)
        .filter(RagEmbeddingProvider.is_active.is_(True))
        .order_by(RagEmbeddingProvider.role)  # 'dense' < 'sparse' alphabetically
        .all()
    )
