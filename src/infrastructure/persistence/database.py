from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from src.config.settings import (
    ASYNC_DB_CONNECT_TIMEOUT,
    ASYNC_DB_MAX_OVERFLOW,
    ASYNC_DB_POOL_RECYCLE,
    ASYNC_DB_POOL_SIZE,
    ASYNC_DB_POOL_TIMEOUT,
    DATABASE_URL,
)
from src.infrastructure.shared.exceptions import MissingDatabaseUrlError

_engine = None
_SessionLocal = None

# 024-async-pipeline-refactor: entirely separate from the sync engine/session
# above — one AsyncSession per per-article unit of work (never shared across
# concurrently-running asyncio.Tasks), all drawn from this one shared factory.
# See specs/024-async-pipeline-refactor/research.md item 2.
#
# Pooling: a bounded QueuePool (SQLAlchemy's default for an async engine when no
# poolclass is passed), NOT NullPool. NullPool opened a fresh asyncpg connection
# — fresh DNS + TCP + TLS + auth — for every `async with sessionmaker()`; a burst
# of concurrent article tasks stampeded asyncio's small default DNS executor and
# getaddrinfo queued past asyncpg's connect timeout, surfacing as a bare
# TimeoutError that failed the article. A real pool reuses connections within a
# run and hard-caps concurrency at pool_size + max_overflow. One process = one
# event loop (each CLI entrypoint does a single asyncio.run()); pool_pre_ping is
# the safety net if a pooled connection is ever seen from a different loop.
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
        _async_engine = create_async_engine(
            _to_asyncpg_url(DATABASE_URL),
            pool_size=ASYNC_DB_POOL_SIZE,
            max_overflow=ASYNC_DB_MAX_OVERFLOW,
            pool_timeout=ASYNC_DB_POOL_TIMEOUT,
            pool_recycle=ASYNC_DB_POOL_RECYCLE,
            pool_pre_ping=True,
            connect_args={"timeout": ASYNC_DB_CONNECT_TIMEOUT},
        )
        _AsyncSessionLocal = async_sessionmaker(bind=_async_engine, expire_on_commit=False)
    return _AsyncSessionLocal


async def prewarm_async_engine(connections: int | None = None) -> None:
    """Open ``connections`` real connections (default: ``ASYNC_DB_POOL_SIZE``)
    once, sequentially, and hand them straight back to the pool.

    The QueuePool switch alone doesn't stop the *first* Barrier-1 fan-out from
    racing: the pool starts empty, so the first ``TEXT_STAGE_CONCURRENCY`` tasks
    each open a brand-new asyncpg connection at the same instant, and their
    getaddrinfo calls stampede asyncio's default executor past the connect
    timeout. Pre-warming here means that fan-out checks out warm connections
    instead. Best-effort: a connection that can't be opened is skipped so a
    transient blip during warm-up doesn't abort startup. Call once, after
    ``get_async_sessionmaker()``, inside the run's event loop.
    """
    from sqlalchemy import text

    get_async_sessionmaker()  # ensure _async_engine is built
    if _async_engine is None:  # engine couldn't be built — nothing to warm
        return
    n = ASYNC_DB_POOL_SIZE if connections is None else connections
    held = []
    try:
        for _ in range(max(0, n)):
            try:
                conn = await _async_engine.connect()
            except Exception:
                break
            held.append(conn)
            await conn.execute(text("SELECT 1"))
    finally:
        for conn in held:
            await conn.close()


async def dispose_async_engine() -> None:
    """Close the async engine's pooled connections and reset the module state.

    Call once at the end of a run (inside the same asyncio.run() that built the
    engine) so pooled asyncpg connections are closed cleanly rather than being
    torn down by process exit. Idempotent — a no-op if the engine was never
    built.
    """
    global _async_engine, _AsyncSessionLocal
    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        _AsyncSessionLocal = None


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
