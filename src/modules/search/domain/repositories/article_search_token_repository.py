from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID

# The language key the original (untranslated) core.articles title/content is indexed
# under — every other language key is an ArticleTranslation.language.
ORIGINAL_LANGUAGE = "en"

SourceKey = Tuple[UUID, str]  # (article_id, language)


@dataclass(frozen=True)
class TokenSource:
    """The text one (article, language) row is tokenized from."""
    article_id: UUID
    language: str
    topic_id: UUID
    title: str
    content: Optional[str]
    source_updated_at: Optional[datetime]  # translation's updated_at; None for the original


@dataclass(frozen=True)
class ArticleTokens:
    article_id: UUID
    language: str
    topic_id: UUID
    tokens: List[str]
    source_updated_at: Optional[datetime]


class ArticleSearchTokenRepository(ABC):
    """Domain port for intelligence.article_search_tokens (the per-(article, language)
    token rows backing exact-match search) and the read models derived from it.

    An (article, language) source is *eligible* when its article is not merged away,
    has a topic, and has an Analysis row (text-stage processing actually completed —
    see RebuildSearchIndexUseCase), and, for a non-original language, when that
    ArticleTranslation still exists."""

    @abstractmethod
    def delete_ineligible(self) -> int:
        """Delete every row whose source is no longer eligible. Returns rows deleted."""
        ...

    @abstractmethod
    def find_stale_keys(self, include_fresh: bool = False) -> List[SourceKey]:
        """Eligible sources whose row is missing, has a different topic_id than its
        article, or (translations) a source_updated_at that no longer matches the
        translation's updated_at. `include_fresh=True` returns every eligible source
        instead — a forced re-tokenize, e.g. after a tokenizer/stopword change."""
        ...

    @abstractmethod
    def load_sources(self, keys: List[SourceKey]) -> List[TokenSource]:
        ...

    @abstractmethod
    def upsert(self, rows: List[ArticleTokens]) -> None:
        """Insert-or-replace rows keyed by (article_id, language), committed."""
        ...

    @abstractmethod
    def refresh_term_counts(self) -> None:
        """Refresh intelligence.search_terms (autocomplete's Postgres-fallback term list)."""
        ...

    @abstractmethod
    def term_counts_by_topic(self, min_doc_freq: int) -> Dict[UUID, Dict[str, int]]:
        """topic_id -> {term: distinct articles containing it in any language}, keeping
        only terms at or above `min_doc_freq` — the Redis autocomplete trie's input,
        which (unlike search_terms) has never been split by language."""
        ...
