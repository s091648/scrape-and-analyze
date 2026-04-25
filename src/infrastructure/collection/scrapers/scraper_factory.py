from src.shared.logging import get_logger
from src.modules.collection.domain.entities import ScraperSetting
from src.modules.collection.domain.factories import ScraperFactory
from src.modules.collection.domain.value_objects.selector_config import (
    ArxivConfig,
    BlogConfig,
    RssConfig,
)
from .base_scraper import BaseScraper
from .rss_scraper import RssScraper
from .blog_scraper import BlogScraper
from .arxiv_scraper import ArxivScraper

logger = get_logger(__name__)


class ConcreteScraperFactory(ScraperFactory):
    """Creates the appropriate BaseScraper for a given ScraperSetting."""

    def create_for(self, setting: ScraperSetting) -> BaseScraper:
        cfg = setting.selector_config

        if isinstance(cfg, RssConfig):
            return RssScraper(
                url=setting.url,
                source=setting.source,
                keywords=setting.keywords,
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
                # Prefer topic-level keywords from DB; fall back to selector_config legacy field.
                keywords=setting.keywords or cfg.keywords,
                categories=cfg.categories,
                topic_id=setting.topic_id,
                prompt_override=setting.prompt_override,
            )

        logger.warning("unknown_source_type", source_type=setting.source_type)
        raise ValueError(f"Unsupported source_type: {setting.source_type}")
