"""
SQLAlchemy implementation for ScraperSetting queries.

Provides both standalone functions (for backward compat) and a
SqlAlchemyScraperSettingRepository class that implements the domain ABC.

src/config/__init__.py delegates to the standalone functions for backward
compatibility; RunScraperUseCase receives the class via DI.
"""
import structlog
from typing import Any, Dict, List, Optional

from src.domain.repositories.scraper_setting_repository import ScraperSettingRepository

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


class SqlAlchemyScraperSettingRepository(ScraperSettingRepository):
    """
    Class-based implementation injected into RunScraperUseCase.
    Delegates query logic to the standalone functions above so there is
    a single source of truth for the SQL.
    """

    def __init__(self, session=None) -> None:
        self._session = session  # None → functions open their own session

    def get_sources_due(self) -> List[Dict[str, Any]]:
        return get_sources_due(session=self._session)

    def mark_scraped(self, source_id: str) -> None:
        from sqlalchemy import text

        own_session = False
        session = self._session
        if session is None:
            from src.infrastructure.persistence.db import get_session
            session = get_session()
            own_session = True

        try:
            session.execute(
                text(
                    "UPDATE scraper_settings SET last_scraped_at = NOW() WHERE id = :id"
                ),
                {"id": source_id},
            )
            session.commit()
            logger.info("source_marked_scraped", source_id=source_id)
        finally:
            if own_session:
                session.close()
