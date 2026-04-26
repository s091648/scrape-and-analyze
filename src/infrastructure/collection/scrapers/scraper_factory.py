from src.shared.logging import get_logger
from src.modules.collection.domain.entities import ScraperSetting
from src.modules.collection.domain.factories import ScraperFactory
from src.modules.collection.domain.value_objects import (
    ArxivConfig,
    BlogConfig,
    RssConfig,
)
from src.modules.collection.domain.value_objects.scraper_keyword import (
    ArxivCategory,
    ArxivKeyword,
    RssKeyword,
)
from .base_scraper import BaseScraper
from .rss_scraper import RssScraper
from .blog_scraper import BlogScraper
from .arxiv_scraper import ArxivScraper

logger = get_logger(__name__)


def _extract(items, vo_type, attr: str) -> list | None:
    """Return a list of `attr` values for keyword_items matching vo_type, or None if empty."""
    if not items:
        return None
    result = [getattr(k, attr) for k in items if isinstance(k, vo_type)]
    return result if result else None


class ConcreteScraperFactory(ScraperFactory):
    """Creates the appropriate BaseScraper for a given ScraperSetting."""

    def create_for(self, setting: ScraperSetting) -> BaseScraper:
        cfg = setting.selector_config

        if isinstance(cfg, RssConfig):
            return RssScraper(
                url=setting.url,
                source=setting.source,
                keywords=_extract(setting.keyword_items, RssKeyword, "keyword"),
                topic_id=setting.topic_id,
                prompt_override=setting.prompt_override,
            )

        if isinstance(cfg, BlogConfig):
            return BlogScraper(
                base_url=setting.url,
                source=setting.source,
                selectors=cfg.selectors,
                topic_id=setting.topic_id,
                prompt_override=setting.prompt_override,
            )

        if isinstance(cfg, ArxivConfig):
            return ArxivScraper(
                max_results=cfg.max_results,
                days_back=cfg.days_back,
                keywords=_extract(setting.keyword_items, ArxivKeyword, "keyword"),
                categories=_extract(setting.keyword_items, ArxivCategory, "keyword"),
                topic_id=setting.topic_id,
                prompt_override=setting.prompt_override,
            )

        logger.warning("unknown_source_type", source_type=setting.source_type)
        raise ValueError(f"Unsupported source_type: {setting.source_type}")
