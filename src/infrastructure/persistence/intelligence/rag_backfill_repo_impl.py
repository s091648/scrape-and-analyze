from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.modules.intelligence.domain.repositories.rag_backfill_repository import RagBackfillRepository
from src.shared.domain.entities import Article

# Mirrors the "skip trivially short content" heuristic scripts/backfill_rag_embeddings.py
# already used — not worth chunking/embedding a handful of words.
_MIN_CONTENT_CHARS = 50


class SqlAlchemyRagBackfillRepository(RagBackfillRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_pending(self, limit: int) -> List[Article]:
        from models.article import Article as ArticleModel

        rows = (
            self._session.query(ArticleModel)
            .filter(ArticleModel.has_vectors.is_(False))
            .filter(ArticleModel.merged_into_id.is_(None))
            .filter(func.length(func.trim(ArticleModel.content)) >= _MIN_CONTENT_CHARS)
            .order_by(ArticleModel.scraped_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_entity(row) for row in rows]

    @staticmethod
    def _to_entity(row) -> Article:
        return Article(
            id=row.id,
            url=row.url,
            url_hash=row.url_hash,
            source=row.source,
            title=row.title,
            content=row.content,
            published_at=row.published_at,
            scraped_at=row.scraped_at,
            metadata=row.metadata_ or {},
            topic_id=row.topic_id,
            original_source=row.original_source,
        )
