from collections import defaultdict
from typing import Dict, List
from uuid import UUID

from sqlalchemy import delete, exists, func, literal, select, text, tuple_, union_all
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.modules.search.domain.repositories.article_search_token_repository import (
    ORIGINAL_LANGUAGE, ArticleSearchTokenRepository, ArticleTokens, SourceKey, TokenSource,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


def _eligible_article_conditions():
    from models.analysis import Analysis
    from models.article import Article

    return (
        Article.merged_into_id.is_(None),
        Article.topic_id.isnot(None),
        exists().where(Analysis.article_id == Article.id),
    )


class SqlAlchemyArticleSearchTokenRepository(ArticleSearchTokenRepository):
    """ORM/Core implementation. Every statement except the materialized-view refresh goes
    through the ORM models, so the integration harness's schema_translate_map routes it
    to the isolated test schema like any other repository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def delete_ineligible(self) -> int:
        from models.article import Article
        from models.article_search_token import ArticleSearchToken as Ast
        from models.article_translation import ArticleTranslation

        article_gone = delete(Ast).where(
            ~exists().where(Article.id == Ast.article_id, *_eligible_article_conditions())
        )
        translation_gone = delete(Ast).where(
            Ast.language != ORIGINAL_LANGUAGE,
            ~exists().where(
                ArticleTranslation.article_id == Ast.article_id,
                ArticleTranslation.language == Ast.language,
            ),
        )
        try:
            deleted = self._session.execute(article_gone).rowcount
            deleted += self._session.execute(translation_gone).rowcount
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return deleted

    def find_stale_keys(self, include_fresh: bool = False) -> List[SourceKey]:
        from models.article import Article
        from models.article_search_token import ArticleSearchToken as Ast
        from models.article_translation import ArticleTranslation

        original = select(Article.id, literal(ORIGINAL_LANGUAGE)).where(*_eligible_article_conditions())
        translated = (
            select(ArticleTranslation.article_id, ArticleTranslation.language)
            .join(Article, Article.id == ArticleTranslation.article_id)
            .where(*_eligible_article_conditions())
        )
        if not include_fresh:
            original = original.where(~exists().where(
                Ast.article_id == Article.id,
                Ast.language == ORIGINAL_LANGUAGE,
                Ast.topic_id == Article.topic_id,
            ))
            translated = translated.where(~exists().where(
                Ast.article_id == ArticleTranslation.article_id,
                Ast.language == ArticleTranslation.language,
                Ast.topic_id == Article.topic_id,
                Ast.source_updated_at.isnot_distinct_from(ArticleTranslation.updated_at),
            ))
        rows = self._session.execute(union_all(original, translated)).all()
        return [(row[0], row[1]) for row in rows]

    def load_sources(self, keys: List[SourceKey]) -> List[TokenSource]:
        from models.article import Article
        from models.article_translation import ArticleTranslation

        original_ids = [article_id for article_id, language in keys if language == ORIGINAL_LANGUAGE]
        translated_keys = [key for key in keys if key[1] != ORIGINAL_LANGUAGE]
        sources: List[TokenSource] = []

        if original_ids:
            rows = self._session.execute(
                select(Article.id, Article.topic_id, Article.title, Article.content)
                .where(Article.id.in_(original_ids))
            ).all()
            sources.extend(
                TokenSource(article_id=r.id, language=ORIGINAL_LANGUAGE, topic_id=r.topic_id,
                            title=r.title, content=r.content, source_updated_at=None)
                for r in rows
            )
        if translated_keys:
            rows = self._session.execute(
                select(
                    ArticleTranslation.article_id, ArticleTranslation.language, Article.topic_id,
                    ArticleTranslation.title, ArticleTranslation.content, ArticleTranslation.updated_at,
                )
                .join(Article, Article.id == ArticleTranslation.article_id)
                .where(tuple_(ArticleTranslation.article_id, ArticleTranslation.language).in_(translated_keys))
            ).all()
            sources.extend(
                TokenSource(article_id=r.article_id, language=r.language, topic_id=r.topic_id,
                            title=r.title, content=r.content, source_updated_at=r.updated_at)
                for r in rows
            )
        return sources

    def upsert(self, rows: List[ArticleTokens]) -> None:
        from models.article_search_token import ArticleSearchToken as Ast

        if not rows:
            return
        stmt = pg_insert(Ast).values([
            {
                "article_id": r.article_id, "language": r.language, "topic_id": r.topic_id,
                "tokens": r.tokens, "source_updated_at": r.source_updated_at,
            }
            for r in rows
        ])
        stmt = stmt.on_conflict_do_update(
            index_elements=[Ast.article_id, Ast.language],
            set_={
                "topic_id": stmt.excluded.topic_id,
                "tokens": stmt.excluded.tokens,
                "source_updated_at": stmt.excluded.source_updated_at,
                "indexed_at": func.now(),
            },
        )
        try:
            self._session.execute(stmt)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def refresh_term_counts(self) -> None:
        # Same reasoning as RefreshTagArticleCountsUseCase: CONCURRENTLY can't run
        # inside a transaction block, so this uses its own AUTOCOMMIT connection, and
        # keeps the view readable (old contents) while it runs. Raw SQL against the real
        # schema name — a materialized view isn't an ORM model.
        engine = self._session.get_bind()
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY intelligence.search_terms"))

    def term_counts_by_topic(self, min_doc_freq: int) -> Dict[UUID, Dict[str, int]]:
        from models.article_search_token import ArticleSearchToken as Ast

        # unnest() can't sit in a GROUP BY directly, so expand in a subquery first.
        expanded = select(
            Ast.topic_id, Ast.article_id, func.unnest(Ast.tokens).label("term"),
        ).subquery()
        article_count = func.count(func.distinct(expanded.c.article_id))
        rows = self._session.execute(
            select(expanded.c.topic_id, expanded.c.term, article_count)
            .group_by(expanded.c.topic_id, expanded.c.term)
            .having(article_count >= min_doc_freq)
        ).all()
        result: Dict[UUID, Dict[str, int]] = defaultdict(dict)
        for topic_id, term, count in rows:
            result[topic_id][term] = count
        return dict(result)
