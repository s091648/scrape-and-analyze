from src.shared.logging import get_logger
from src.modules.collection.domain.entities import ScraperSetting
from src.modules.collection.domain.factories import ScraperFactory
from .base_scraper import BaseScraper
from .rss_scraper import RssScraper
from .blog_scraper import BlogScraper
from .arxiv_scraper import ArxivScraper

logger = get_logger(__name__)


class ConcreteScraperFactory(ScraperFactory):
    """Creates the appropriate BaseScraper for a given ScraperSetting."""

    def create_for(self, setting: ScraperSetting) -> BaseScraper:
        cfg = setting.selector_config or {}

        if setting.source_type == "rss":
            # DB keywords take precedence; fall back to selector_config["keywords"] for compat
            keywords = setting.keywords if setting.keywords is not None else cfg.get("keywords") or None
            return RssScraper(
                url=setting.url,
                source=setting.source,
                keywords=keywords,
                topic_id=setting.topic_id,
                prompt_override=setting.prompt_override,
            )

        if setting.source_type == "blog":
            return BlogScraper(
                base_url=setting.url,
                source=setting.source,
                selectors=cfg.get("selectors", {}),
                topic_id=setting.topic_id,
                prompt_override=setting.prompt_override,
            )

        if setting.source_type == "arxiv":
            return ArxivScraper(
                max_results=cfg.get("max_results", 30),
                days_back=cfg.get("days_back", 7),
                keywords=cfg.get("keywords") or None,
                categories=cfg.get("categories") or None,
                topic_id=setting.topic_id,
                prompt_override=setting.prompt_override,
            )

        logger.warning("unknown_source_type", source_type=setting.source_type)
        raise ValueError(f"Unsupported source_type: {setting.source_type}")
