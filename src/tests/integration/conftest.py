import pytest
import os
from dataclasses import dataclass
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
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{TEST_SCHEMA}"'))
        conn.commit()

    # Test engine — all unqualified table references route to the test schema
    engine = create_engine(
        base_url,
        # Include `public` so types installed by extensions (eg. pgvector)
        # are visible when the test schema is set as the first search_path.
        connect_args={"options": f"-csearch_path={TEST_SCHEMA},public"},
    )

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

    # Create all tables inside the test schema
    Base.metadata.create_all(engine)

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
