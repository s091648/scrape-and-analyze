"""Unit tests for SqlAlchemyRagBackfillRepository."""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.infrastructure.persistence.intelligence.rag_backfill_repo_impl import SqlAlchemyRagBackfillRepository
from src.shared.domain.entities import Article


@pytest.fixture
def session():
    return MagicMock()


@pytest.fixture
def repo(session):
    return SqlAlchemyRagBackfillRepository(session)


def _mock_row(**overrides):
    row = MagicMock()
    row.id = overrides.get("id", uuid.uuid4())
    row.url = overrides.get("url", "https://example.com/a")
    row.url_hash = overrides.get("url_hash", "hash123")
    row.source = overrides.get("source", "rss")
    row.title = overrides.get("title", "Title")
    row.content = overrides.get("content", "Body text")
    row.published_at = overrides.get("published_at", datetime(2026, 1, 1, tzinfo=timezone.utc))
    row.scraped_at = overrides.get("scraped_at", datetime(2026, 1, 2, tzinfo=timezone.utc))
    row.metadata_ = overrides.get("metadata_", {"doi": "10.1234/a"})
    row.topic_id = overrides.get("topic_id", None)
    row.original_source = overrides.get("original_source", None)
    return row


class TestFindPending:
    def test_returns_empty_when_no_matches(self, repo, session):
        query = session.query.return_value
        query.filter.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.all.return_value = []

        result = repo.find_pending(limit=100)

        assert result == []

    def test_maps_rows_to_article_entities(self, repo, session):
        article_id = uuid.uuid4()
        row = _mock_row(id=article_id)

        query = session.query.return_value
        query.filter.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.all.return_value = [row]

        result = repo.find_pending(limit=100)

        assert len(result) == 1
        article = result[0]
        assert isinstance(article, Article)
        assert article.id == article_id
        assert article.url == row.url
        assert article.metadata == {"doi": "10.1234/a"}

    def test_defaults_null_metadata_to_empty_dict(self, repo, session):
        row = _mock_row(metadata_=None)

        query = session.query.return_value
        query.filter.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.all.return_value = [row]

        result = repo.find_pending(limit=100)

        assert result[0].metadata == {}

    def test_applies_limit(self, repo, session):
        query = session.query.return_value
        query.filter.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.all.return_value = []

        repo.find_pending(limit=42)

        query.limit.assert_called_once_with(42)
