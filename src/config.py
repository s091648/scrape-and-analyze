import os
import structlog
import tomllib
from typing import List, Dict, Any

logger = structlog.get_logger(__name__)

# Environment variables
DATABASE_URL = os.environ.get('DATABASE_URL', '')
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')


def get_sources(source_type: str, session=None) -> List[Dict[str, Any]]:
    """Get active sources from the database by source_type ('rss', 'blog', 'arxiv')."""
    from backend.models.scraper_setting import ScraperSetting

    own_session = False
    if session is None:
        from src.database import get_session
        session = get_session()
        own_session = True

    try:
        settings = session.query(ScraperSetting).filter(
            ScraperSetting.source_type == source_type,
            ScraperSetting.is_active == True,
        ).all()

        if not settings:
            logger.critical(
                "no_active_sources_found",
                source_type=source_type,
                action="returning_empty_list",
            )
            return []

        result = []
        for s in settings:
            entry = {
                "id": str(s.id),
                "source": s.name,
                "url": s.url,
                "source_type": s.source_type,
                "selector_config": s.selector_config,
            }
            if s.source_type == "blog" and s.selector_config:
                entry["base_url"] = s.url
                entry["selectors"] = s.selector_config
            result.append(entry)
        return result
    finally:
        if own_session:
            session.close()


def get_sources_due(session=None) -> List[Dict[str, Any]]:
    """Return active sources whose last scrape time has exceeded their frequency interval."""
    from backend.models.scraper_setting import ScraperSetting
    from sqlalchemy import or_, text

    own_session = False
    if session is None:
        from src.database import get_session
        session = get_session()
        own_session = True

    try:
        settings = session.query(ScraperSetting).filter(
            ScraperSetting.is_active == True,
            or_(
                ScraperSetting.last_scraped_at == None,
                text("NOW() - last_scraped_at > frequency * INTERVAL '1 hour'"),
            )
        ).all()

        result = []
        for s in settings:
            entry = {
                "id": str(s.id),
                "source": s.name,
                "url": s.url,
                "source_type": s.source_type,
                "selector_config": s.selector_config or {},
                "frequency": s.frequency,
            }
            if s.source_type == "blog" and s.selector_config:
                entry["base_url"] = s.url
                entry["selectors"] = s.selector_config
            result.append(entry)
        return result
    finally:
        if own_session:
            session.close()


def validate_config() -> None:
    """Validate required configuration at startup"""
    errors = []

    if not os.environ.get('DATABASE_URL', DATABASE_URL):
        errors.append("DATABASE_URL is required")

    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")


def load_providers(path: str = None) -> List[Dict[str, Any]]:
    """Load provider definitions from providers.toml (sorted by priority)."""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'providers.toml')
    with open(path, 'rb') as f:
        data = tomllib.load(f)
    providers = data.get('providers', [])
    return sorted(providers, key=lambda p: p['priority'])
