import os
from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy import create_engine, not_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

_engine = None
_SessionLocal = None


def create_engine_with_nullpool():
    """Create SQLAlchemy engine with NullPool"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")
    return create_engine(database_url, poolclass=NullPool)


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


def find_missing_analyses(session) -> List:
    """Find articles that have no analysis."""
    from models.article import Article
    from models.analysis import Analysis

    analyzed_ids = session.query(Analysis.article_id).all()
    analyzed_ids = [aid[0] for aid in analyzed_ids]

    if not analyzed_ids:
        return session.query(Article).all()

    return session.query(Article).filter(
        not_(Article.id.in_(analyzed_ids))
    ).all()


def scan_missing_analyses(session, min_age_hours: int = 1) -> List:
    """Find articles older than min_age_hours that have no analysis (zombie detection)."""
    from models.article import Article
    from models.analysis import Analysis

    cutoff = datetime.now(timezone.utc) - timedelta(hours=min_age_hours)

    analyzed_ids = session.query(Analysis.article_id).all()
    analyzed_ids = [aid[0] for aid in analyzed_ids]

    query = session.query(Article).filter(
        Article.scraped_at < cutoff
    )

    if analyzed_ids:
        query = query.filter(not_(Article.id.in_(analyzed_ids)))
    else:
        pass

    return query.all()
