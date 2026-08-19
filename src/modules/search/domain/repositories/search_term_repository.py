from abc import ABC, abstractmethod
from typing import Dict, Set, Tuple
from uuid import UUID


class SearchTermRepository(ABC):
    """Domain interface for the term->article inverted index persistence
    (intelligence.search_terms + intelligence.search_term_articles — 023-article-search
    follow-up)."""

    @abstractmethod
    def replace_all(self, topic_term_articles: Dict[Tuple[UUID, str, str], Set[UUID]]) -> None:
        """Atomically replace every row in both tables — FR-008's full-rebuild-not-
        incremental contract, mirroring the Redis index's own replace-not-merge rebuild.

        Key is (topic_id, term, language); value is the set of distinct article_ids that
        term occurs in (within that topic+language). occurrence_count is derived as
        len(article_ids) — callers must not pre-filter by a minimum frequency here, since
        this table backs exact-match retrieval's completeness guarantee, not just
        autocomplete suggestion quality (that filtering happens separately, only on the
        Redis trie's input)."""
        ...
