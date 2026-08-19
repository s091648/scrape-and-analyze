"""Rebuild the entire autocomplete term index from scratch — FR-008: no incremental
update, just re-derive everything from core.articles each scheduled scrape cycle."""
from collections import defaultdict, Counter
from typing import Any
from uuid import UUID

from src.modules.search.domain.services.tokenizer import tokenize
from src.shared.logging import get_logger

logger = get_logger(__name__)


class RebuildSearchIndexUseCase:
    def __init__(self, session: Any, search_term_repo: Any, search_index_gateway: Any, min_doc_freq: int = 2) -> None:
        self._session = session
        self._search_term_repo = search_term_repo
        self._search_index_gateway = search_index_gateway
        self._min_doc_freq = min_doc_freq

    def execute(self) -> dict:
        from models.article import Article
        from models.article_translation import ArticleTranslation

        # Left-joined so translated (e.g. zh-TW) title/content feed the same term
        # extraction as the original — otherwise autocomplete/search would only ever
        # surface terms in whatever language the article was originally scraped in
        # (almost always English), even though ArticleTranslation exists and the
        # tokenizer explicitly supports zh-TW.
        rows = (
            self._session.query(
                Article.id, Article.topic_id, Article.title, Article.content,
                ArticleTranslation.language, ArticleTranslation.title, ArticleTranslation.content,
            )
            .outerjoin(ArticleTranslation, ArticleTranslation.article_id == Article.id)
            .filter(Article.merged_into_id.is_(None))
            # Untopic'd articles are excluded from search entirely — FR-009 scopes both
            # search and autocomplete by topic, and intelligence.search_terms.topic_id
            # is NOT NULL (no meaningful "global" partition to place them in).
            .filter(Article.topic_id.isnot(None))
            .all()
        )

        # Aggregated by article id first (not per row) — an article with N translations
        # produces N joined rows, and counting per-row would inflate its term document
        # frequency by however many translations it has.
        article_topic: dict[UUID, UUID] = {}
        # Language-blind union of every language's terms for one article — feeds the
        # Redis autocomplete trie below, which (unlike intelligence.search_terms) has
        # never split suggestions by language (023-article-search follow-up design
        # discussion: the Redis structure stays as-is, only the Postgres side splits).
        article_terms_blind: dict[UUID, set[str]] = defaultdict(set)
        # Same terms, kept split by the language they actually occurred in — feeds
        # intelligence.search_terms/search_term_articles, since a non-English exact-match
        # query can only ever literally match that language's translation, never a
        # different language's text (same asymmetry _is_exact_match already has in
        # backend/services/search_service.py).
        article_terms_by_lang: dict[UUID, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

        for article_id, topic_id, title, content, t_language, t_title, t_content in rows:
            article_topic[article_id] = topic_id
            original_terms = tokenize(f"{title} {content}")
            article_terms_blind[article_id] |= original_terms
            article_terms_by_lang[article_id]["en"] |= original_terms
            if t_title:
                translated_terms = tokenize(f"{t_title} {t_content or ''}")
                article_terms_blind[article_id] |= translated_terms
                article_terms_by_lang[article_id][t_language] |= translated_terms

        # ── Redis trie input: topic -> term -> distinct article count ───────────────
        # Filtered by min_doc_freq — this bounds *suggestion quality* (a term only one
        # article ever uses isn't a useful autocomplete suggestion), not findability.
        topic_term_counts: dict[UUID, Counter] = defaultdict(Counter)
        for article_id, terms in article_terms_blind.items():
            for term in terms:
                topic_term_counts[article_topic[article_id]][term] += 1  # one distinct article == +1
        redis_topic_terms: dict[UUID, dict[str, int]] = {
            topic_id: {term: count for term, count in counts.items() if count >= self._min_doc_freq}
            for topic_id, counts in topic_term_counts.items()
        }

        # ── Postgres inverted-index input: (topic, term, language) -> {article_ids} ──
        # Deliberately UNFILTERED by min_doc_freq: this is exact-match retrieval's
        # completeness guarantee (023-article-search follow-up), not an autocomplete
        # suggestion list — a term used in only one article must still be exact-match
        # findable even though it'd never be worth suggesting as you type.
        topic_term_articles: dict[tuple[UUID, str, str], set[UUID]] = defaultdict(set)
        for article_id, terms_by_lang in article_terms_by_lang.items():
            topic_id = article_topic[article_id]
            for language, terms in terms_by_lang.items():
                for term in terms:
                    topic_term_articles[(topic_id, term, language)].add(article_id)

        # Write order matters (research.md): Postgres (durable) first, Redis (fast-path
        # cache) second — a crash between the two leaves Redis merely stale, never ahead
        # of the source-of-truth fallback it exists to protect against.
        self._search_term_repo.replace_all(topic_term_articles)
        self._search_index_gateway.rebuild(redis_topic_terms)

        term_count = sum(len(counts) for counts in topic_term_counts.values())
        stats = {"article_count": len(article_terms_blind), "topic_count": len(redis_topic_terms), "term_count": term_count}
        logger.info("search_index_rebuilt", **stats)
        return stats
