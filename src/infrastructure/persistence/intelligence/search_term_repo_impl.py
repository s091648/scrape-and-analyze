import uuid as uuid_lib
from typing import Dict, Set, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from src.modules.search.domain.repositories.search_term_repository import SearchTermRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemySearchTermRepository(SearchTermRepository):
    """SQLAlchemy ORM implementation — wholesale replace of both intelligence.search_terms
    and intelligence.search_term_articles in one transaction (FR-008: full rebuild, not
    an incremental merge). ORM, not raw SQL: this table pair moved from shared/
    search_index/ (raw-SQL-only, no ORM model — matching vectors.article_chunks) to here
    once query-time evidence showed backend/services/search_service.py needed a term-
    >article lookup for exact-match retrieval, at which point going through models/
    (already shared between src/ and backend/) was simpler than inventing a second raw-
    SQL access path just for that (023-article-search follow-up)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_all(self, topic_term_articles: Dict[Tuple[UUID, str, str], Set[UUID]]) -> None:
        from models.search_term import SearchTerm
        from models.search_term_article import SearchTermArticle

        # Children before parents — explicit within this one transaction rather than
        # relying on ON DELETE CASCADE to fire mid-transaction in delete order.
        self._session.query(SearchTermArticle).delete(synchronize_session=False)
        self._session.query(SearchTerm).delete(synchronize_session=False)

        search_terms = []
        search_term_articles = []
        for (topic_id, term, language), article_ids in topic_term_articles.items():
            if not article_ids:
                continue
            # Generated client-side (not left to SearchTerm.id's ORM default) so the
            # child SearchTermArticle rows below can reference it without an
            # intermediate flush()-per-term round trip.
            term_id = uuid_lib.uuid4()
            search_terms.append(SearchTerm(
                id=term_id, topic_id=topic_id, term=term, language=language,
                occurrence_count=len(article_ids),
            ))
            search_term_articles.extend(
                SearchTermArticle(search_term_id=term_id, article_id=article_id)
                for article_id in article_ids
            )

        self._session.add_all(search_terms)
        self._session.add_all(search_term_articles)

        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        logger.info(
            "search_terms_replaced",
            term_count=len(search_terms),
            article_link_count=len(search_term_articles),
        )
