import os
from datetime import datetime, timedelta, timezone
from typing import List
from uuid import UUID
from sqlalchemy import create_engine
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


def get_session() -> Session:
    """Get a new database session"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


def has_analysis(session, article_id: UUID) -> bool:
    """Check if article has analysis"""
    from src.models.analysis import Analysis
    return session.query(Analysis).filter_by(article_id=article_id).first() is not None


def find_missing_analyses(session) -> List:
    """Find articles without analysis"""
    from src.models.article import Article
    from src.models.analysis import Analysis
    return session.query(Article).outerjoin(Analysis).filter(Analysis.id == None).all()


def scan_missing_analyses(session, min_age_hours: int = 1) -> List:
    """
    Find articles that should have analysis but don't (zombie records).
    Only considers articles older than min_age_hours to avoid race conditions.
    """
    from src.models.article import Article
    from src.models.analysis import Analysis

    cutoff = datetime.now(timezone.utc) - timedelta(hours=min_age_hours)

    return session.query(Article)\
        .outerjoin(Analysis)\
        .filter(Analysis.id == None)\
        .filter(Article.scraped_at < cutoff)\
        .all()


def find_recent_failures(session, hours: int = 24) -> List:
    """Find unresolved failures from last N hours"""
    from src.models.failed_task import FailedTask
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return session.query(FailedTask).filter(
        FailedTask.resolved == False,
        FailedTask.failed_at >= cutoff
    ).all()
