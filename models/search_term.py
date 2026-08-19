from sqlalchemy import Column, String, Text, Integer, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid

from models.base import Base
from models.db_schema import DbSchema


class SearchTerm(Base):
    """One distinct term counted within a (topic, language) — the compact, pre-expansion
    autocomplete term list (023-article-search) and, via SearchTermArticle, the source of
    truth for exact-match retrieval (023-article-search follow-up: term->article inverted
    index). `occurrence_count` is the number of distinct articles (within its topic+
    language) the term occurs in.

    `language` splits this table the same way ArticleTranslation/AnalysesTranslation/
    TagsTranslation/TagGroupDefinitionsTranslation do — one row per language rather than a
    single row mixing every language's terms together — so a language-scoped Postgres
    fallback lookup (find_matching()) can filter on (topic_id, language) with a plain
    index instead of scanning across every language's terms."""
    __tablename__ = 'search_terms'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(UUID(as_uuid=True), nullable=False)
    term = Column(Text, nullable=False)
    language = Column(String(10), nullable=False)
    occurrence_count = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint('topic_id', 'term', 'language', name='uq_search_terms_topic_term_language'),
        Index('idx_search_terms_topic_language', 'topic_id', 'language'),
        {'schema': DbSchema.INTELLIGENCE.value},
    )
