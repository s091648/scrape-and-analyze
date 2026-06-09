from typing import Optional
from uuid import UUID

from src.modules.collection.domain.entities import ArxivMetadata
from src.modules.collection.domain.repositories import ArxivMetadataRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyArxivMetadataRepository(ArxivMetadataRepository):
    """SQLAlchemy implementation of the ArxivMetadataRepository interface."""

    def __init__(self, session) -> None:
        self._session = session

    def save(self, meta: ArxivMetadata) -> ArxivMetadata:
        """Persist arXiv metadata and return the entity with DB-generated fields."""
        from models.arxiv_metadata import ArxivMetadata as ArxivMetadataModel

        row = ArxivMetadataModel(
            article_id=meta.article_id,
            arxiv_id=meta.arxiv_id,
            authors=meta.authors or [],
            pdf_available=meta.pdf_available,
            sections=meta.sections or {},
        )
        self._session.add(row)
        self._session.flush()
        logger.info("arxiv_metadata_saved", article_id=str(meta.article_id))
        return self._to_entity(row)

    def find_by_article_id(self, article_id: UUID) -> Optional[ArxivMetadata]:
        """Look up arXiv metadata by article ID; returns None if not found."""
        from models.arxiv_metadata import ArxivMetadata as ArxivMetadataModel

        row = self._session.query(ArxivMetadataModel).filter_by(article_id=article_id).first()
        return self._to_entity(row) if row else None

    @staticmethod
    def _to_entity(row) -> ArxivMetadata:
        """Convert an ORM ArxivMetadata row to a domain ArxivMetadata entity."""
        return ArxivMetadata(
            article_id=row.article_id,
            id=row.id,
            arxiv_id=row.arxiv_id,
            authors=list(row.authors or []),
            pdf_available=bool(row.pdf_available),
            sections=dict(row.sections or {}),
        )
