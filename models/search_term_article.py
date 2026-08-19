from sqlalchemy import Column, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from models.base import Base
from models.db_schema import DbSchema


class SearchTermArticle(Base):
    """Term -> article inverted index (023-article-search follow-up): one row per
    (search_term, article) pair the term literally occurs in. Backs the AND-intersection
    exact-match retrieval path in backend/services/search_service.py — a multi-token
    query's exact-match candidate set is the intersection of each token's article_id set
    here, entirely independent of RRF/vector retrieval's candidate_k bound (so an exact
    match RRF's sparse/dense candidate lists never surfaced is still findable).

    Populated for every distinct term RebuildSearchIndexUseCase's tokenizer finds,
    regardless of SEARCH_MIN_DOC_FREQ — that threshold only gates what's *suggested* by
    autocomplete (SearchTerm.occurrence_count / the Redis trie); it must not also gate
    what's *findable* via exact match, or a term that happens to occur in only one
    article would silently vanish from exact_match_only results even though the
    substring genuinely occurs there."""
    __tablename__ = 'search_term_articles'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_term_id = Column(UUID(as_uuid=True), ForeignKey('intelligence.search_terms.id', ondelete='CASCADE'), nullable=False)
    article_id = Column(UUID(as_uuid=True), ForeignKey('core.articles.id', ondelete='CASCADE'), nullable=False)

    search_term = relationship("SearchTerm", backref="articles")
    article = relationship("Article", backref="search_term_articles")

    __table_args__ = (
        UniqueConstraint('search_term_id', 'article_id', name='uq_search_term_articles_term_article'),
        Index('idx_search_term_articles_article_id', 'article_id'),
        {'schema': DbSchema.INTELLIGENCE.value},
    )
