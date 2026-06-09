"""Unit tests for backend/services/scraper_keyword_service.py"""
import uuid
from unittest.mock import MagicMock, patch

import pytest


def _mock_keyword(**kwargs):
    k = MagicMock()
    k.id = kwargs.get("id", uuid.uuid4())
    k.topic_id = kwargs.get("topic_id", uuid.uuid4())
    k.keyword_type = kwargs.get("keyword_type", "rss")
    k.keyword = kwargs.get("keyword", "machine learning")
    return k


# ---------------------------------------------------------------------------
# list_keywords
# ---------------------------------------------------------------------------

def test_list_keywords_returns_all_for_topic():
    from backend.services.scraper_keyword_service import list_keywords

    kw = _mock_keyword()
    topic_id = uuid.uuid4()

    db = MagicMock()
    q = db.query.return_value
    q.filter_by.return_value = q
    q.order_by.return_value.all.return_value = [kw]

    with patch("models.scraper_keyword.ScraperKeyword"):
        result = list_keywords(db, topic_id=topic_id)

    assert result == [kw]


def test_list_keywords_no_type_filter_calls_filter_by_once():
    from backend.services.scraper_keyword_service import list_keywords

    topic_id = uuid.uuid4()
    db = MagicMock()
    q = db.query.return_value
    q.filter_by.return_value = q
    q.order_by.return_value.all.return_value = []

    with patch("models.scraper_keyword.ScraperKeyword"):
        list_keywords(db, topic_id=topic_id)

    # Only one filter_by call (for topic_id)
    assert q.filter_by.call_count == 1


def test_list_keywords_with_type_filter_calls_filter_by_twice():
    from backend.services.scraper_keyword_service import list_keywords

    topic_id = uuid.uuid4()
    db = MagicMock()
    q = db.query.return_value
    q.filter_by.return_value = q
    q.order_by.return_value.all.return_value = []

    with patch("models.scraper_keyword.ScraperKeyword"):
        list_keywords(db, topic_id=topic_id, keyword_type="arxiv")

    # Two filter_by calls: topic_id, then keyword_type
    assert q.filter_by.call_count == 2


def test_list_keywords_empty():
    from backend.services.scraper_keyword_service import list_keywords

    db = MagicMock()
    q = db.query.return_value
    q.filter_by.return_value = q
    q.order_by.return_value.all.return_value = []

    with patch("models.scraper_keyword.ScraperKeyword"):
        result = list_keywords(db, topic_id=uuid.uuid4())

    assert result == []


# ---------------------------------------------------------------------------
# create_keyword
# ---------------------------------------------------------------------------

def test_create_keyword_success():
    from backend.services.scraper_keyword_service import create_keyword

    topic_id = uuid.uuid4()
    mock_kw = _mock_keyword(topic_id=topic_id, keyword="bert", keyword_type="arxiv")

    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None  # no duplicate

    with patch("models.scraper_keyword.ScraperKeyword") as MockKw:
        MockKw.return_value = mock_kw
        result = create_keyword(db, topic_id=topic_id, keyword_type="arxiv", keyword="bert")

    db.add.assert_called_once_with(mock_kw)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(mock_kw)
    assert result is mock_kw


def test_create_keyword_duplicate_raises_409():
    from backend.services.scraper_keyword_service import create_keyword
    from fastapi import HTTPException

    topic_id = uuid.uuid4()
    existing = _mock_keyword(topic_id=topic_id, keyword="bert", keyword_type="arxiv")

    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = existing

    with patch("models.scraper_keyword.ScraperKeyword"):
        with pytest.raises(HTTPException) as exc:
            create_keyword(db, topic_id=topic_id, keyword_type="arxiv", keyword="bert")

    assert exc.value.status_code == 409
    db.add.assert_not_called()


# ---------------------------------------------------------------------------
# delete_keyword
# ---------------------------------------------------------------------------

def test_delete_keyword_found_returns_true():
    from backend.services.scraper_keyword_service import delete_keyword

    kw_id = uuid.uuid4()
    mock_kw = _mock_keyword(id=kw_id)

    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = mock_kw

    with patch("models.scraper_keyword.ScraperKeyword"):
        result = delete_keyword(db, kw_id)

    db.delete.assert_called_once_with(mock_kw)
    db.commit.assert_called_once()
    assert result is True


def test_delete_keyword_not_found_returns_false():
    from backend.services.scraper_keyword_service import delete_keyword

    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None

    with patch("models.scraper_keyword.ScraperKeyword"):
        result = delete_keyword(db, uuid.uuid4())

    assert result is False
    db.delete.assert_not_called()
    db.commit.assert_not_called()
