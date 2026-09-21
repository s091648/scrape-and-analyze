"""Refresh intelligence.tag_article_counts (a materialized view — see
alembic/versions/28_add_tag_article_counts_mv.py) once per completed scrape
pipeline run, mirroring RebuildSearchIndexUseCase's role for search_terms."""
from typing import Any

from sqlalchemy import text

from src.shared.logging import get_logger

logger = get_logger(__name__)


class RefreshTagArticleCountsUseCase:
    def __init__(self, session: Any) -> None:
        self._session = session

    def execute(self) -> None:
        # REFRESH MATERIALIZED VIEW CONCURRENTLY cannot run inside a transaction
        # block (same restriction as CREATE INDEX CONCURRENTLY), so this opens its
        # own connection off the session's engine in autocommit mode rather than
        # reusing self._session's ambient transaction. CONCURRENTLY (needs the
        # unique index the migration creates) keeps GET /tag-groups readable
        # against the old data for the ~second this takes, instead of taking an
        # ACCESS EXCLUSIVE lock that would block those reads.
        engine = self._session.get_bind()
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY intelligence.tag_article_counts"
            ))
        logger.info("tag_article_counts_refreshed")
