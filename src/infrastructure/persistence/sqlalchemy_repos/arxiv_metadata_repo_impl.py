from typing import Optional
from uuid import UUID

from src.domain.entities.arxiv_metadata import ArxivMetadataEntity
from src.domain.repositories.arxiv_metadata_repository import ArxivMetadataRepository
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyArxivMetadataRepository(ArxivMetadataRepository):

    def __init__(self, session) -> None:
        self._session = session

    def save(self, meta: ArxivMetadataEntity) -> ArxivMetadataEntity:
        from models.arxiv_metadata import ArxivMetadata
        row = ArxivMetadata(
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

    def find_by_article_id(self, article_id: UUID) -> Optional[ArxivMetadataEntity]:
        from models.arxiv_metadata import ArxivMetadata
        row = self._session.query(ArxivMetadata).filter_by(article_id=article_id).first()
        return self._to_entity(row) if row else None

    @staticmethod
    def _to_entity(row) -> ArxivMetadataEntity:
        return ArxivMetadataEntity(
            id=row.id,
            article_id=row.article_id,
            arxiv_id=row.arxiv_id,
            authors=list(row.authors or []),
            pdf_available=bool(row.pdf_available),
            sections=dict(row.sections or {}),
        )
