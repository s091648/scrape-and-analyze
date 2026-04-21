import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
import uuid


def test_engine_uses_nullpool():
    with patch.dict('os.environ', {'DATABASE_URL': 'postgresql://test:test@localhost/test'}):
        from src.infrastructure.persistence.database import create_engine_with_nullpool
        from sqlalchemy.pool import NullPool
        engine = create_engine_with_nullpool()
        assert isinstance(engine.pool, NullPool)


def test_has_analysis_returns_true_when_exists():
    from src.infrastructure.persistence.database import has_analysis
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = MagicMock()
    result = has_analysis(mock_session, uuid.uuid4())
    assert result is True


def test_has_analysis_returns_false_when_not_exists():
    from src.infrastructure.persistence.database import has_analysis
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = None
    result = has_analysis(mock_session, uuid.uuid4())
    assert result is False


def test_find_missing_analyses_returns_articles_without_analysis():
    from src.infrastructure.persistence.database import find_missing_analyses
    mock_session = MagicMock()
    mock_article = MagicMock()
    mock_session.query.return_value.outerjoin.return_value.filter.return_value.all.return_value = [mock_article]
    result = find_missing_analyses(mock_session)
    assert len(result) == 1


def test_scan_missing_analyses_finds_zombie_records():
    from src.infrastructure.persistence.database import scan_missing_analyses
    mock_session = MagicMock()
    mock_article = MagicMock()
    mock_article.url = 'https://example.com/zombie'
    mock_session.query.return_value.outerjoin.return_value.filter.return_value.filter.return_value.all.return_value = [mock_article]
    result = scan_missing_analyses(mock_session)
    assert len(result) == 1
    assert result[0].url == 'https://example.com/zombie'


def test_find_recent_failures_filters_by_time():
    from src.infrastructure.persistence.database import find_recent_failures
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = []
    result = find_recent_failures(mock_session, hours=24)
    mock_session.query.return_value.filter.assert_called()
    assert result == []