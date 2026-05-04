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


def test_find_recent_failures_filters_by_time():
    from src.infrastructure.persistence.database import find_recent_failures
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = []
    result = find_recent_failures(mock_session, hours=24)
    mock_session.query.return_value.filter.assert_called()
    assert result == []
