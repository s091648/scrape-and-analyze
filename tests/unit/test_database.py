import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
import uuid


def test_engine_uses_nullpool():
    """Engine should use NullPool to avoid connection leaks"""
    with patch.dict('os.environ', {'DATABASE_URL': 'postgresql://test:test@localhost/test'}):
        from src.database import create_engine_with_nullpool
        from sqlalchemy.pool import NullPool

        engine = create_engine_with_nullpool()
        assert isinstance(engine.pool, NullPool)


def test_get_session_returns_session():
    """get_session should return a valid SQLAlchemy session"""
    with patch.dict('os.environ', {'DATABASE_URL': 'postgresql://test:test@localhost/test'}):
        from src.database import get_session
        from sqlalchemy.orm import Session

        session = get_session()
        assert isinstance(session, Session)
        session.close()


def test_has_analysis_returns_true_when_exists():
    """has_analysis should return True when analysis exists"""
    from src.database import has_analysis

    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = MagicMock()

    result = has_analysis(mock_session, uuid.uuid4())
    assert result is True


def test_has_analysis_returns_false_when_not_exists():
    """has_analysis should return False when no analysis"""
    from src.database import has_analysis

    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = None

    result = has_analysis(mock_session, uuid.uuid4())
    assert result is False


def test_find_recent_failures_filters_by_time():
    """find_recent_failures should filter by time window"""
    from src.database import find_recent_failures

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = []

    result = find_recent_failures(mock_session, hours=24)

    mock_session.query.return_value.filter.assert_called()
    assert result == []


def test_find_missing_analyses_returns_articles_without_analysis():
    """find_missing_analyses should return articles that have no analysis"""
    from src.database import find_missing_analyses

    mock_session = MagicMock()
    mock_article = MagicMock()
    mock_session.query.return_value.outerjoin.return_value.filter.return_value.all.return_value = [mock_article]

    result = find_missing_analyses(mock_session)
    assert len(result) == 1


def test_scan_missing_analyses_finds_zombie_records():
    """scan_missing_analyses should find articles without analysis"""
    from src.database import scan_missing_analyses

    mock_session = MagicMock()

    mock_article = MagicMock()
    mock_article.id = 'test-id'
    mock_article.url = 'https://example.com/zombie'

    mock_session.query.return_value.outerjoin.return_value.filter.return_value.filter.return_value.all.return_value = [mock_article]

    result = scan_missing_analyses(mock_session)

    assert len(result) == 1
    assert result[0].url == 'https://example.com/zombie'


def test_scan_missing_analyses_excludes_recent():
    """scan_missing_analyses should only find articles older than threshold"""
    from src.database import scan_missing_analyses

    mock_session = MagicMock()
    mock_session.query.return_value.outerjoin.return_value.filter.return_value.filter.return_value.all.return_value = []

    result = scan_missing_analyses(mock_session, min_age_hours=1)

    assert result == []
