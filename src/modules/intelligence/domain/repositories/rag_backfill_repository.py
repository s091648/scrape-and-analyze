from abc import ABC, abstractmethod
from typing import List

from src.shared.domain.entities import Article


class RagBackfillRepository(ABC):
    """Finds previously-scraped articles not yet ingested into the vector store."""

    @abstractmethod
    def find_pending(self, limit: int) -> List[Article]:
        """Non-tombstoned articles with non-trivial content whose has_vectors
        flag is still FALSE — the flag is kept in sync by a Postgres trigger
        on INSERT into vectors.articles (see migration
        21_add_vectors_schema_and_article_chunks), so this also doubles as
        the retry queue: an article that fails ingestion simply stays FALSE
        and is picked up again on the next run."""
