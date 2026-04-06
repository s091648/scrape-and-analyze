"""
SQLAlchemy implementation for ScraperSetting queries.

These functions are the canonical source going forward.
src/config/__init__.py delegates to them for backward compatibility;
future phases will inject them directly into use cases.
"""
import structlog
from typing import Any, Dict, List, Optional

logger = structlog.get_logger(__name__)


def get_sources(source_type: str, session=None) -> List[Dict[str, Any]]:
    """Return active scraper settings filtered by *source_type*."""
    from models.scraper_setting import ScraperSetting

    own_session = False
    if session is None:
        from src.infrastructure.persistence.db import get_session
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
            entry: Dict[str, Any] = {
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
    """Return active sources whose scrape interval has elapsed."""
    from models.scraper_setting import ScraperSetting
    from sqlalchemy import or_, text

    own_session = False
    if session is None:
        from src.infrastructure.persistence.db import get_session
        session = get_session()
        own_session = True

    try:
        settings = session.query(ScraperSetting).filter(
            ScraperSetting.is_active == True,
            or_(
                ScraperSetting.last_scraped_at == None,
                text(
                    "NOW() - last_scraped_at > frequency * INTERVAL '1 hour'"
                    " - INTERVAL '30 minutes'"
                ),
            ),
        ).all()

        result = []
        for s in settings:
            entry: Dict[str, Any] = {
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
