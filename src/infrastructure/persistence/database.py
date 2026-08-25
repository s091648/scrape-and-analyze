from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from src.config.settings import DATABASE_URL
from src.infrastructure.shared.exceptions import MissingDatabaseUrlError

_engine = None
_SessionLocal = None

# 024-async-pipeline-refactor: entirely separate from the sync engine/session
# above — one AsyncSession per per-article unit of work (never shared across
# concurrently-running asyncio.Tasks), all drawn from this one shared factory.
# See specs/024-async-pipeline-refactor/research.md item 2.
_async_engine: AsyncEngine | None = None
_AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def _to_asyncpg_url(sync_url: str) -> str:
    """Rewrite a psycopg2-style DATABASE_URL ("postgresql://..." or
    "postgresql+psycopg2://...") to the asyncpg driver SQLAlchemy expects
    ("postgresql+asyncpg://...")."""
    if sync_url.startswith("postgresql+psycopg2://"):
        return sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


def get_async_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Get or create the shared async engine + session factory.

    Callers create their own AsyncSession per unit of work via
    `async with get_async_sessionmaker()() as session:` — never share one
    AsyncSession across concurrently-running tasks.
    """
    global _async_engine, _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        if not DATABASE_URL:
            raise MissingDatabaseUrlError("DATABASE_URL environment variable is required")
        _async_engine = create_async_engine(_to_asyncpg_url(DATABASE_URL), poolclass=NullPool)
        _AsyncSessionLocal = async_sessionmaker(bind=_async_engine, expire_on_commit=False)
    return _AsyncSessionLocal


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
