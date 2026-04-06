"""
Backward-compatibility shim for `src.config`.

All new code should import directly from the canonical modules:
  - src.config.settings   → DATABASE_URL, SENTRY_DSN, validate_config
  - src.config.providers  → load_providers
  - src.infrastructure.persistence.sqlalchemy_repos.scraper_setting_repo_impl
                          → get_sources, get_sources_due

This __init__.py re-exports everything so existing imports remain unchanged.
The module-level `logger` is kept here so `patch('src.config.logger')` in
tests continues to work — get_sources / get_sources_due reference it via
their module globals.
"""
import structlog

logger = structlog.get_logger(__name__)

from src.config.settings import DATABASE_URL, SENTRY_DSN, validate_config  # noqa: E402, F401
from src.config.providers import load_providers  # noqa: E402, F401


# ── DB-touching functions (kept here for test backward-compat) ────────────────
# Tests patch `src.config.logger`, which works because these functions are
# defined in this module and look up `logger` from module globals at call time.

def get_sources(source_type: str, session=None):
    """Return active scraper settings filtered by source_type."""
    from models.scraper_setting import ScraperSetting

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


def get_sources_due(session=None):
    """Return active sources whose scrape interval has elapsed."""
    from models.scraper_setting import ScraperSetting
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
                text(
                    "NOW() - last_scraped_at > frequency * INTERVAL '1 hour'"
                    " - INTERVAL '30 minutes'"
                ),
            ),
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
