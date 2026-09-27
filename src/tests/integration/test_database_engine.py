"""Integration tests for src/infrastructure/persistence/database.py — the sync engine /
session factory and the async engine lifecycle (build → prewarm → dispose) every
scraper entrypoint relies on, run against the real DATABASE_URL. Only `SELECT 1` is
executed; no tables are touched.

The module keeps its engines in module globals; each test resets them through
monkeypatch so nothing built here leaks into other tests."""
import pytest
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from src.infrastructure.persistence import database
from src.infrastructure.shared.exceptions import MissingDatabaseUrlError

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _isolated_module_state(monkeypatch):
    for name in ("_engine", "_SessionLocal", "_async_engine", "_AsyncSessionLocal"):
        monkeypatch.setattr(database, name, None)


class TestSyncEngine:
    def test_get_engine_is_a_cached_nullpool_engine(self):
        engine = database.get_engine()

        assert engine is database.get_engine()
        assert isinstance(engine.pool, NullPool)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar() == 1
        engine.dispose()

    def test_get_session_returns_a_working_session(self):
        session = database.get_session()
        try:
            assert session.execute(text("SELECT 1")).scalar() == 1
        finally:
            session.close()
            database.get_engine().dispose()

    def test_missing_database_url_raises(self, monkeypatch):
        monkeypatch.setattr(database, "DATABASE_URL", "")

        with pytest.raises(MissingDatabaseUrlError):
            database.create_engine_with_nullpool()
        with pytest.raises(MissingDatabaseUrlError):
            database.get_async_sessionmaker()


class TestAsyncEngineLifecycle:
    @pytest.mark.asyncio
    async def test_sessionmaker_is_cached_and_usable(self):
        factory = database.get_async_sessionmaker()
        try:
            assert database.get_async_sessionmaker() is factory
            async with factory() as session:
                assert (await session.execute(text("SELECT 1"))).scalar() == 1
        finally:
            await database.dispose_async_engine()

    @pytest.mark.asyncio
    async def test_prewarm_opens_and_returns_pooled_connections(self):
        await database.prewarm_async_engine(connections=2)
        try:
            pool = database._async_engine.pool
            # Every prewarmed connection went straight back to the pool, none still checked out.
            assert pool.checkedout() == 0
            assert pool.checkedin() >= 1
        finally:
            await database.dispose_async_engine()

    @pytest.mark.asyncio
    async def test_prewarm_with_zero_connections_is_a_no_op(self):
        await database.prewarm_async_engine(connections=0)
        try:
            assert database._async_engine.pool.checkedin() == 0
        finally:
            await database.dispose_async_engine()

    @pytest.mark.asyncio
    async def test_dispose_resets_state_and_is_idempotent(self):
        first = database.get_async_sessionmaker()

        await database.dispose_async_engine()
        await database.dispose_async_engine()  # no engine left — must be a no-op

        assert database._async_engine is None and database._AsyncSessionLocal is None
        second = database.get_async_sessionmaker()
        assert second is not first
        await database.dispose_async_engine()


@pytest.mark.parametrize("url, expected", [
    ("postgresql://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
    ("postgresql+psycopg2://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
    ("postgresql+asyncpg://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
])
def test_to_asyncpg_url(url, expected):
    assert database._to_asyncpg_url(url) == expected
