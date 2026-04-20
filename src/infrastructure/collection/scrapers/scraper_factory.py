from src.shared.logging import get_logger
from src.modules.collection.domain.entities import ScraperSetting
from src.modules.collection.domain.factories import ScraperFactory
from src.infrastructure.collection.scrapers.base_scraper import BaseScraper
from src.infrastructure.collection.scrapers.rss_scraper import RssScraper
from src.infrastructure.collection.scrapers.blog_scraper import BlogScraper
from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper

logger = get_logger(__name__)


class ConcreteScraperFactory(ScraperFactory):
    """Creates the appropriate BaseScraper for a given ScraperSetting."""

    def create_for(self, setting: ScraperSetting) -> BaseScraper:
        cfg = setting.selector_config or {}

        if setting.source_type == "rss":
            return RssScraper(
                url=setting.url,
                source=setting.source,
                keywords=cfg.get("keywords") or None,
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
                days_back=cfg.get("days_back", 1),
                keywords=cfg.get("keywords") or None,
                categories=cfg.get("categories") or None,
                topic_id=setting.topic_id,
                prompt_override=setting.prompt_override,
            )

        logger.warning("unknown_source_type", source_type=setting.source_type)
        raise ValueError(f"Unsupported source_type: {setting.source_type}")
