import pytest
import os
from sqlalchemy import create_engine, text
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
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{TEST_SCHEMA}"'))
        conn.commit()

    # Test engine — all unqualified table references route to the test schema
    engine = create_engine(
        base_url,
        connect_args={"options": f"-csearch_path={TEST_SCHEMA}"},
    )

    # Import every non-auth model so their tables are registered before create_all()
    from models.article import Base
    from models.analysis import Analysis          # noqa: F401
    from models.failed_task import FailedTask     # noqa: F401
    from models.tag import Tag                    # noqa: F401
    from models.tag_group import TagGroupDefinition  # noqa: F401
    from models.scraper_setting import ScraperBase, ScraperSetting  # noqa: F401

    # Create all tables inside the test schema
    Base.metadata.create_all(engine)
    ScraperBase.metadata.create_all(engine)

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
