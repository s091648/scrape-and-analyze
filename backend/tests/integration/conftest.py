import os
import time

import pytest
from jose import jwt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_SCHEMA = "backend_test"

os.environ["NEXTAUTH_SECRET"] = "test-secret"
_JWT_SECRET = "test-secret"


@pytest.fixture(scope="session")
def db_engine():
    base_url = os.environ["DATABASE_URL"]

    root_engine = create_engine(base_url)
    with root_engine.connect() as conn:
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{TEST_SCHEMA}"'))
        conn.commit()

    # DDD-bounded-context schemas (016-db-schema-brushup) carry an explicit
    # `schema=` on their Table, so a plain search_path trick can't route them
    # into the isolated test schema — `schema_translate_map` rewrites every
    # compiled `<schema>.<table>` reference (DDL/DML, ORM/Core) to
    # TEST_SCHEMA at execution time. It does NOT apply to raw `text()` SQL —
    # any raw SQL against these tables in application code still targets the
    # real schema (see repo docs / research.md §8 follow-up).
    DDD_SCHEMAS = {"core", "collection", "intelligence", "ai_infra", "user_prefs"}
    schema_translate_map = {schema: TEST_SCHEMA for schema in DDD_SCHEMAS}

    engine = create_engine(
        base_url,
        connect_args={"options": f"-csearch_path={TEST_SCHEMA},public"},
    ).execution_options(schema_translate_map=schema_translate_map)

    from models.base import Base
    from models.topic import Topic                        # noqa: F401
    from models.article import Article                   # noqa: F401
    from models.article_translation import ArticleTranslation  # noqa: F401
    from models.analysis import Analysis                 # noqa: F401
    from models.analyses_translation import AnalysesTranslation  # noqa: F401
    from models.tag import Tag                           # noqa: F401
    from models.tag_group import TagGroupDefinition      # noqa: F401
    from models.tag_translation import TagsTranslation   # noqa: F401
    from models.tag_group_translation import TagGroupDefinitionsTranslation  # noqa: F401
    from models.tag_normalization_suggestion import TagNormalizationSuggestion  # noqa: F401
    from models.scraper_setting import ScraperSetting    # noqa: F401
    from models.llm_provider import LlmProvider          # noqa: F401
    from models.metric_definition import MetricDefinition  # noqa: F401
    from models.metric_provider import MetricProvider    # noqa: F401
    from models.scraper_keyword import ScraperKeyword    # noqa: F401
    from models.failed_task import FailedTask            # noqa: F401
    from models.article_metrics import ArticleMetrics    # noqa: F401
    from models.article_metric_value import ArticleMetricValue  # noqa: F401
    from models.weekly_report import WeeklyReport        # noqa: F401
    from models.weekly_report_translation import WeeklyReportTranslation  # noqa: F401
    from models.user_subscription import (               # noqa: F401
        UserTopicSubscription,
        UserNotificationSettings,
        UserArticleFavorite,
    )

    # Exclude auth-schema tables (User) — those exist only in public.
    # Also exclude tables pinned to a fixed, migration-owned schema (eg.
    # `vectors.article_chunks`) — those already exist in the real database
    # via alembic and aren't isolated per-test like the default-schema tables.
    # Use checkfirst=False for the per-test-schema tables so SQLAlchemy creates
    # them even when identically-named tables exist in the public schema
    # (which would otherwise cause has_table() to return True and skip creation).
    FIXED_SCHEMAS = {"auth", "vectors"}
    non_auth = [t for t in Base.metadata.sorted_tables if t.schema not in FIXED_SCHEMAS]
    Base.metadata.create_all(engine, tables=non_auth, checkfirst=False)

    yield engine

    engine.dispose()
    with root_engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{TEST_SCHEMA}" CASCADE'))
        conn.commit()
    root_engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """
    Wraps each test in an outer transaction that is always rolled back.
    join_transaction_mode="create_savepoint" ensures that endpoint-level
    db.commit() calls commit to a savepoint (not the real DB), so they
    don't escape the outer rollback.
    """
    connection = db_engine.connect()
    outer_tx = connection.begin()
    session = sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )()
    yield session
    session.close()
    outer_tx.rollback()
    connection.close()


@pytest.fixture
def api_client(db_session):
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.database import get_db

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def admin_token() -> str:
    payload = {"sub": "admin", "role": "admin", "exp": int(time.time()) + 3600}
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def user_token(user_id: str = "user-uuid-001") -> str:
    payload = {"sub": user_id, "role": "user", "exp": int(time.time()) + 3600}
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")
