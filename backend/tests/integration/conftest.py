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
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{TEST_SCHEMA}"'))
        conn.commit()

    engine = create_engine(
        base_url,
        connect_args={"options": f"-csearch_path={TEST_SCHEMA}"},
    )

    from models.base import Base
    from models.topic import Topic                        # noqa: F401
    from models.article import Article                   # noqa: F401
    from models.analysis import Analysis                 # noqa: F401
    from models.tag import Tag                           # noqa: F401
    from models.tag_group import TagGroupDefinition      # noqa: F401
    from models.scraper_setting import ScraperSetting    # noqa: F401
    from models.llm_provider import LlmProvider          # noqa: F401

    Base.metadata.create_all(engine)

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
