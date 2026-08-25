import pytest
import pytest_asyncio
import os
from dataclasses import dataclass
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

TEST_SCHEMA = "test_integration"

os.environ.setdefault('LLM_API_KEY', 'test-key')
os.environ.setdefault('SKIP_CONFIG_VALIDATION', 'true')


@pytest.fixture(scope="session")
def db_engine():
    base_url = os.environ["DATABASE_URL"]

    # Root engine (no search_path) — used only for schema creation/teardown
    root_engine = create_engine(base_url)
    with root_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{TEST_SCHEMA}"'))
        conn.commit()

    # DDD-bounded-context schemas (016-db-schema-brushup) carry an explicit
    # `schema=` on their Table, so SQLAlchemy compiles fully-qualified names
    # for them regardless of `search_path` — a plain search_path trick (as
    # used for the originally-unqualified tables below) can no longer route
    # them into the isolated test schema. `schema_translate_map` is SQLAlchemy's
    # supported mechanism for exactly this: it rewrites every compiled
    # `<schema>.<table>` reference (DDL and DML alike, for ORM/Core queries)
    # to `TEST_SCHEMA.<table>` at execution time, collapsing all 5 schemas
    # into the one isolated per-test schema. NOTE: it does NOT apply to raw
    # `text()` SQL — any raw SQL against these tables in application code is
    # written against the real schema name and will see the real database,
    # not the isolated one (see repo docs / research.md §8 follow-up).
    DDD_SCHEMAS = {"core", "collection", "intelligence", "ai_infra", "user_prefs"}
    schema_translate_map = {schema: TEST_SCHEMA for schema in DDD_SCHEMAS}

    # Test engine — unqualified table references route to the test schema via
    # search_path; explicit-schema tables route there via schema_translate_map.
    engine = create_engine(
        base_url,
        # Include `public` so types installed by extensions (eg. pgvector)
        # are visible when the test schema is set as the first search_path.
        connect_args={"options": f"-csearch_path={TEST_SCHEMA},public"},
    ).execution_options(schema_translate_map=schema_translate_map)

    # Import every non-auth model so their tables are registered before create_all()
    from models.base import Base
    from models.article import Article              # noqa: F401
    from models.topic import Topic                  # noqa: F401
    from models.analysis import Analysis            # noqa: F401
    from models.analyses_translation import AnalysesTranslation  # noqa: F401
    from models.failed_task import FailedTask       # noqa: F401
    from models.tag import Tag                      # noqa: F401
    from models.tag_group import TagGroupDefinition  # noqa: F401
    from models.scraper_setting import ScraperSetting  # noqa: F401
    from models.scraper_keyword import ScraperKeyword  # noqa: F401
    from models.article_translation import ArticleTranslation  # noqa: F401
    from models.article_metrics import ArticleMetrics  # noqa: F401
    from models.article_metric_value import ArticleMetricValue  # noqa: F401
    from models.tag_translation import TagsTranslation  # noqa: F401
    from models.tag_group_translation import TagGroupDefinitionsTranslation  # noqa: F401
    from models.tag_normalization_suggestion import TagNormalizationSuggestion  # noqa: F401
    from models.weekly_report import WeeklyReport  # noqa: F401
    from models.weekly_report_translation import WeeklyReportTranslation  # noqa: F401
    from models.llm_provider import LlmProvider  # noqa: F401
    from models.metric_definition import MetricDefinition  # noqa: F401
    from models.metric_provider import MetricProvider  # noqa: F401
    from models.user_subscription import (  # noqa: F401
        UserTopicSubscription, UserNotificationSettings, UserArticleFavorite,
    )

    # Create all tables inside the test schema.
    # checkfirst=False is required: has_table() would otherwise resolve
    # unqualified table names via search_path, find the identically-named
    # table in `public` (the real dev database), and skip creation here —
    # silently routing every insert in this suite into `public` instead of
    # the isolated test schema. Only `auth`/`vectors` remain excluded — those
    # predate DbSchema, are truly owned by alembic migrations, and are left
    # untranslated (few tests touch them directly).
    FIXED_SCHEMAS = {"auth", "vectors"}
    tables = [t for t in Base.metadata.sorted_tables if t.schema not in FIXED_SCHEMAS]
    Base.metadata.create_all(engine, tables=tables, checkfirst=False)

    yield engine

    # Teardown: drop the entire test schema (leaves production data untouched)
    engine.dispose()
    with root_engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{TEST_SCHEMA}" CASCADE'))
        conn.commit()
    root_engine.dispose()


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# 024-async-pipeline-refactor: async counterpart of db_engine/db_session above,
# pointed at the SAME isolated test_integration schema (created once by the
# session-scoped db_engine fixture) via a separate asyncpg-driven engine —
# mirrors get_async_sessionmaker()'s relationship to the sync engine in
# src/infrastructure/persistence/database.py.
#
# Function-scoped (NOT session-scoped like db_engine): asyncpg connections are
# bound to the event loop they were created on, and pytest-asyncio gives each
# test function its own event loop by default — a session-scoped async engine
# would be reused across loops and fail with "attached to a different loop" /
# "another operation is in progress". Engine construction itself is cheap
# (lazy, no connection opened until first use), so recreating it per test costs
# nothing meaningful.
@pytest_asyncio.fixture
async def async_db_session(db_engine):
    from src.infrastructure.persistence.database import _to_asyncpg_url

    base_url = os.environ["DATABASE_URL"]
    DDD_SCHEMAS = {"core", "collection", "intelligence", "ai_infra", "user_prefs"}
    schema_translate_map = {schema: TEST_SCHEMA for schema in DDD_SCHEMAS}

    engine = create_async_engine(
        _to_asyncpg_url(base_url),
        connect_args={"server_settings": {"search_path": f"{TEST_SCHEMA},public"}},
    ).execution_options(schema_translate_map=schema_translate_map)

    Session = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.rollback()

    await engine.dispose()


@dataclass
class TagGroupRef:
    """Lightweight reference to a TagGroupDefinition row (avoids detached-instance errors)."""
    name: str
    display_name: str
    topic_id: object = None  # UUID of the owning topic


@pytest.fixture(scope="session")
def test_topic(db_engine):
    """Shared Topic row for tests that need tag group FK references."""
    from models.topic import Topic
    Session = sessionmaker(bind=db_engine)
    session = Session()
    try:
        existing = session.query(Topic).filter_by(name="test-topic").first()
        if not existing:
            t = Topic(name="test-topic", display_name="Test Topic",
                      color_hex="#3B82F6", sort_order=1)
            session.add(t)
            session.commit()
            topic_id = t.id
        else:
            topic_id = existing.id
    finally:
        session.close()
    return topic_id


@pytest.fixture(scope="session")
def tag_group(db_engine, test_topic):
    """Create a shared TagGroupDefinition for tests that need tag FK references."""
    from models.tag_group import TagGroupDefinition

    name = "test_technology"
    Session = sessionmaker(bind=db_engine)
    session = Session()
    try:
        existing = session.query(TagGroupDefinition).filter_by(
            name=name, topic_id=test_topic
        ).first()
        if not existing:
            tg = TagGroupDefinition(
                name=name,
                display_name="Test Technology",
                description="Tag group used in integration tests",
                color_hex="#3B82F6",
                sort_order=1,
                topic_id=test_topic,
            )
            session.add(tg)
            session.commit()
    finally:
        session.close()

    return TagGroupRef(name=name, display_name="Test Technology", topic_id=test_topic)
