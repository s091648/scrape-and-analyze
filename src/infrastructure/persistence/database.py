from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from src.config.settings import DATABASE_URL
from src.infrastructure.shared.exceptions import MissingDatabaseUrlError

_engine = None
_SessionLocal = None


def create_engine_with_nullpool():
    """Create SQLAlchemy engine with NullPool"""
    if not DATABASE_URL:
        raise MissingDatabaseUrlError("DATABASE_URL environment variable is required")
    return create_engine(DATABASE_URL, poolclass=NullPool)


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
