"""Bring the search read models up to date once per scrape cycle (FR-008).

intelligence.article_search_tokens (exact-match search) is synced incrementally: only
(article, language) sources that are new, changed topic, or whose translation was
updated since they were last indexed get re-tokenized, and rows whose source stopped
being eligible are deleted. Staleness is detected from the data itself rather than from
pipeline events, so articles/translations written outside the pipeline (make translate,
retry-failed, dedup reconcile) are picked up the same way, and a missed run self-heals
on the next one.

The two derived read models are then recomputed from that table — no re-tokenizing:
intelligence.search_terms (materialized view, autocomplete's Postgres fallback) and the
Redis autocomplete trie (still rebuilt wholesale, since its flattened suffix/prefix keys
are far simpler to regenerate than to patch)."""
from typing import Any

from src.modules.search.domain.repositories.article_search_token_repository import ArticleTokens
from src.modules.search.domain.services.tokenizer import tokenize
from src.shared.logging import get_logger

logger = get_logger(__name__)

_BATCH_SIZE = 200


class RebuildSearchIndexUseCase:
    def __init__(
        self, search_token_repo: Any, search_index_gateway: Any,
        min_doc_freq: int = 2, batch_size: int = _BATCH_SIZE,
    ) -> None:
        self._search_token_repo = search_token_repo
        self._search_index_gateway = search_index_gateway
        self._min_doc_freq = min_doc_freq
        self._batch_size = batch_size

    def execute(self, full: bool = False) -> dict:
        """`full=True` re-tokenizes every eligible source (e.g. after a tokenizer or
        stopword change) — rows are overwritten in place, so search never sees an empty
        index mid-run."""
        # Eligibility (see ArticleSearchTokenRepository) requires an Analysis row:
        # Article.title/content exist from the moment ProcessScrapedArticleUseCase saves
        # them, so a permanently-failed analyze would otherwise still surface in search.
        deleted_count = self._search_token_repo.delete_ineligible()

        stale_keys = self._search_token_repo.find_stale_keys(include_fresh=full)
        for start in range(0, len(stale_keys), self._batch_size):
            sources = self._search_token_repo.load_sources(stale_keys[start:start + self._batch_size])
            self._search_token_repo.upsert([
                ArticleTokens(
                    article_id=s.article_id, language=s.language, topic_id=s.topic_id,
                    tokens=sorted(tokenize(f"{s.title} {s.content or ''}")),
                    source_updated_at=s.source_updated_at,
                )
                for s in sources
            ])

        # Write order matters (research.md): Postgres (durable) first, Redis (fast-path
        # cache) second — a crash between the two leaves Redis merely stale, never ahead
        # of the source-of-truth fallback it exists to protect against.
        self._search_token_repo.refresh_term_counts()
        topic_terms = self._search_token_repo.term_counts_by_topic(self._min_doc_freq)
        self._search_index_gateway.rebuild(topic_terms)

        stats = {
            "indexed_count": len(stale_keys),
            "deleted_count": deleted_count,
            "topic_count": len(topic_terms),
            "term_count": sum(len(terms) for terms in topic_terms.values()),
        }
        logger.info("search_index_rebuilt", full=full, **stats)
        return stats
