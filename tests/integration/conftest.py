import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use test database
# Use test database (postgres service in Docker, localhost for local runs)
os.environ['DATABASE_URL'] = 'postgresql://digital_twins:digital_twins@postgres:5432/digital_twins_test'
os.environ['LLM_API_KEY'] = 'test-key'
os.environ['SKIP_CONFIG_VALIDATION'] = 'true'


@pytest.fixture(scope='session')
def db_engine():
    """Create database engine for tests"""
    from src.models.article import Base
    engine = create_engine(os.environ['DATABASE_URL'])
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine):
    """Create a new database session for each test"""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()
