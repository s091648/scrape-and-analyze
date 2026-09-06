import pytest
from unittest.mock import patch


def test_get_async_sessionmaker_returns_distinct_sessions():
    import src.infrastructure.persistence.database as db_module

    with patch.object(db_module, "_async_engine", None), \
         patch.object(db_module, "_AsyncSessionLocal", None), \
         patch.object(db_module, "DATABASE_URL", "postgresql://test:test@localhost/test"):
        factory = db_module.get_async_sessionmaker()
        session_a = factory()
        session_b = factory()
        assert session_a is not session_b


def test_get_async_sessionmaker_is_a_singleton_factory():
    import src.infrastructure.persistence.database as db_module

    with patch.object(db_module, "_async_engine", None), \
         patch.object(db_module, "_AsyncSessionLocal", None), \
         patch.object(db_module, "DATABASE_URL", "postgresql://test:test@localhost/test"):
        factory_a = db_module.get_async_sessionmaker()
        factory_b = db_module.get_async_sessionmaker()
        assert factory_a is factory_b


def test_get_async_sessionmaker_raises_when_database_url_missing():
    import src.infrastructure.persistence.database as db_module
    from src.infrastructure.shared.exceptions import MissingDatabaseUrlError

    with patch.object(db_module, "_async_engine", None), \
         patch.object(db_module, "_AsyncSessionLocal", None), \
         patch.object(db_module, "DATABASE_URL", ""):
        with pytest.raises(MissingDatabaseUrlError):
            db_module.get_async_sessionmaker()


def test_to_asyncpg_url_rewrites_sync_scheme():
    from src.infrastructure.persistence.database import _to_asyncpg_url

    assert _to_asyncpg_url("postgresql://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"
    assert _to_asyncpg_url("postgresql+psycopg2://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"


def test_async_engine_uses_a_bounded_pool_not_nullpool():
    """Regression guard: the async engine must NOT be NullPool (which opened a
    fresh asyncpg connection — fresh DNS + TLS + auth — per session and, under a
    burst of concurrent article tasks, starved asyncio's DNS executor into
    connect timeouts). It must be a bounded pool sized from settings."""
    import src.infrastructure.persistence.database as db_module
    from sqlalchemy.pool import NullPool
    from src.config import settings

    with patch.object(db_module, "_async_engine", None), \
         patch.object(db_module, "_AsyncSessionLocal", None), \
         patch.object(db_module, "DATABASE_URL", "postgresql://test:test@localhost/test"):
        db_module.get_async_sessionmaker()
        pool = db_module._async_engine.sync_engine.pool
        assert not isinstance(pool, NullPool)
        assert pool.size() == settings.ASYNC_DB_POOL_SIZE
        assert pool._max_overflow == settings.ASYNC_DB_MAX_OVERFLOW


@pytest.mark.asyncio
async def test_dispose_async_engine_resets_module_state():
    import src.infrastructure.persistence.database as db_module

    with patch.object(db_module, "_async_engine", None), \
         patch.object(db_module, "_AsyncSessionLocal", None), \
         patch.object(db_module, "DATABASE_URL", "postgresql://test:test@localhost/test"):
        db_module.get_async_sessionmaker()
        assert db_module._async_engine is not None

        await db_module.dispose_async_engine()
        assert db_module._async_engine is None
        assert db_module._AsyncSessionLocal is None

        # Idempotent — a second call (engine already gone) is a no-op.
        await db_module.dispose_async_engine()
