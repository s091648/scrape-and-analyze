from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from models.base import Base
from models.db_schema import DbSchema


class ArticleSearchToken(Base):
    """One row per (article, language): the distinct, filtered terms `tokenize()`
    (shared/search_index/tokenizer.py) extracted from that article's text in that
    language — the original title+content under "en", each ArticleTranslation under its
    own language. Replaces the old intelligence.search_terms + search_term_articles
    table pair (migration 29_add_article_search_tokens).

    The GIN index on `tokens` IS the term->article inverted index: exact-match retrieval
    (backend/services/search_service.py) is `tokens @> ARRAY[...query tokens]`, which GIN
    answers by intersecting each token's posting list — the same AND-intersection the old
    GROUP BY/HAVING query did by hand, maintained by Postgres on every row write.

    Kept current incrementally, not rebuilt: RebuildSearchIndexUseCase only re-tokenizes
    (article, language) pairs that have no row yet, whose topic changed, or whose
    translation's `updated_at` no longer matches `source_updated_at`, and deletes rows
    whose article/translation stopped being eligible. `source_updated_at` is NULL for the
    "en" row (core.articles title/content are never updated after insert).

    intelligence.search_terms (autocomplete's term list with per-(topic, language)
    article counts) is a materialized view derived from this table — see the migration."""
    __tablename__ = 'article_search_tokens'

    article_id = Column(
        UUID(as_uuid=True), ForeignKey('core.articles.id', ondelete='CASCADE'), primary_key=True,
    )
    language = Column(String(10), primary_key=True)
    topic_id = Column(UUID(as_uuid=True), nullable=False)
    tokens = Column(ARRAY(Text), nullable=False)
    source_updated_at = Column(DateTime(timezone=True), nullable=True)
    indexed_at = Column(DateTime(timezone=True), nullable=False, server_default=text('now()'))

    __table_args__ = (
        Index('idx_article_search_tokens_tokens', 'tokens', postgresql_using='gin'),
        Index('idx_article_search_tokens_topic_language', 'topic_id', 'language'),
        {'schema': DbSchema.INTELLIGENCE.value},
    )
