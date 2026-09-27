"""SqlAlchemyArticleSearchTokenRepository's write paths against a mocked Session — the
transaction handling (commit on success, rollback + re-raise on failure) and the empty-
batch short-circuit. The SQL itself is exercised against Postgres in
src/tests/integration/test_search_index_and_cache_redis.py."""
import uuid
from unittest.mock import MagicMock

import pytest

from src.infrastructure.persistence.intelligence.article_search_token_repo_impl import (
    SqlAlchemyArticleSearchTokenRepository,
)
from src.modules.search.domain.repositories.article_search_token_repository import (
    ORIGINAL_LANGUAGE, ArticleTokens,
)


def _tokens() -> ArticleTokens:
    return ArticleTokens(
        article_id=uuid.uuid4(), language=ORIGINAL_LANGUAGE, topic_id=uuid.uuid4(),
        tokens=["alpha", "beta"], source_updated_at=None,
    )


def test_delete_ineligible_sums_both_deletes_and_commits():
    session = MagicMock()
    session.execute.side_effect = [MagicMock(rowcount=3), MagicMock(rowcount=2)]

    deleted = SqlAlchemyArticleSearchTokenRepository(session).delete_ineligible()

    assert deleted == 5
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


def test_delete_ineligible_rolls_back_and_reraises_on_failure():
    session = MagicMock()
    session.execute.side_effect = RuntimeError("db down")

    with pytest.raises(RuntimeError, match="db down"):
        SqlAlchemyArticleSearchTokenRepository(session).delete_ineligible()

    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_upsert_with_no_rows_touches_nothing():
    session = MagicMock()

    SqlAlchemyArticleSearchTokenRepository(session).upsert([])

    session.execute.assert_not_called()
    session.commit.assert_not_called()


def test_upsert_commits_one_statement_for_the_whole_batch():
    session = MagicMock()

    SqlAlchemyArticleSearchTokenRepository(session).upsert([_tokens(), _tokens()])

    session.execute.assert_called_once()
    session.commit.assert_called_once()


def test_upsert_rolls_back_and_reraises_on_failure():
    session = MagicMock()
    session.commit.side_effect = RuntimeError("conflict")

    with pytest.raises(RuntimeError, match="conflict"):
        SqlAlchemyArticleSearchTokenRepository(session).upsert([_tokens()])

    session.rollback.assert_called_once()
