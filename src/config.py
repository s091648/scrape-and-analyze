import os
import structlog
import tomllib
from typing import List, Dict, Any

logger = structlog.get_logger(__name__)

# Environment variables
DATABASE_URL = os.environ.get('DATABASE_URL', '')
LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'claude')
LLM_MODEL = os.environ.get('LLM_MODEL', 'claude-sonnet-4-20250514')
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')


def get_sources(schedule_type: str, session=None) -> List[Dict[str, Any]]:
    """Get active sources from the database based on schedule type."""
    from backend.models.scraper_setting import ScraperSetting
    from sqlalchemy import and_

    own_session = False
    if session is None:
        from src.database import get_session
        session = get_session()
        own_session = True

    try:
        settings = session.query(ScraperSetting).filter(
            and_(
                ScraperSetting.frequency == schedule_type,
                ScraperSetting.is_active == True,
            )
        ).all()

        if not settings:
            logger.critical(
                "no_active_sources_found",
                schedule_type=schedule_type,
                action="returning_empty_list",
            )
            return []

        result = []
        for s in settings:
            entry = {"source": s.name, "url": s.url}
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

    db_url = os.environ.get('DATABASE_URL', DATABASE_URL)
    api_key = os.environ.get('LLM_API_KEY', LLM_API_KEY)

    if not db_url:
        errors.append("DATABASE_URL is required")

    if not api_key:
        errors.append("LLM_API_KEY is required")

    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")


def load_providers(path: str = None) -> List[Dict[str, Any]]:
    """Load provider definitions from providers.toml (sorted by priority)."""
    if path is None:
        path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'providers.toml')
    with open(path, 'rb') as f:
        data = tomllib.load(f)
    providers = data.get('providers', [])
    return sorted(providers, key=lambda p: p['priority'])
