import os
from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

_engine = None
_SessionLocal = None


def create_engine_with_nullpool():
    """Create SQLAlchemy engine with NullPool"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")
    return create_engine(database_url, poolclass=NullPool)


def get_engine():
    """Get or create the database engine"""
    global _engine
    if _engine is None:
        _engine = create_engine_with_nullpool()
    return _engine


def init_db() -> None:
    """Create all tables if they don't exist (idempotent)"""
    from models.base import Base
    Base.metadata.create_all(get_engine())


def get_session() -> Session:
    """Get a new database session"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


def find_recent_failures(session, hours: int = 24) -> List:
    """Find unresolved failures from last N hours"""
    from models.failed_task import FailedTask
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return session.query(FailedTask).filter(
        FailedTask.resolved == False,
        FailedTask.failed_at >= cutoff
    ).all()
