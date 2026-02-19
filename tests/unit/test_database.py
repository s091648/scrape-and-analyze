import pytest
from unittest.mock import patch


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
