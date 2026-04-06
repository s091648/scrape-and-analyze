"""
ScraperService — builds scrapers from source config dicts and runs the dispatcher.

Extracted from main.py:run_scrape_cycle().
Belongs in the ingestion bounded context because it knows about scraper types.
"""
from typing import Any, Callable, Dict, List, Optional

from src.ingestion.models.scraped_article import ScrapedArticle
from src.ingestion.scrapers.base_scraper import BaseScraper
from src.pipeline.dispatcher import ScrapeDispatcher
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ScraperService:
    """
    Translates source config dicts into concrete scraper instances and
    delegates execution to ScrapeDispatcher.
    """

    def __init__(self, dispatcher: ScrapeDispatcher) -> None:
        self._dispatcher = dispatcher

    def run(
        self,
        sources: List[Dict[str, Any]],
        on_result: Callable[[ScrapedArticle], None],
    ) -> List[Dict[str, Any]]:
        """
        Build scrapers from *sources*, run the dispatcher, and return the
        source configs that were successfully initialised.

        The returned list is used by the caller to mark sources as scraped.
        """
        scrapers_with_sources: List[tuple[BaseScraper, Dict[str, Any]]] = []

        for source in sources:
            scraper = self._build_scraper(source)
            if scraper is not None:
                scrapers_with_sources.append((scraper, source))

        if not scrapers_with_sources:
            return []

        self._dispatcher.run(
            scrapers=[s for s, _ in scrapers_with_sources],
            on_result=on_result,
        )

        return [src for _, src in scrapers_with_sources]

    # ── private ───────────────────────────────────────────────────────────

    def _build_scraper(self, source: Dict[str, Any]) -> Optional[BaseScraper]:
        """Instantiate the correct scraper for *source*. Returns None on failure."""
        from src.ingestion.scrapers.rss_scraper import RssScraper
        from src.ingestion.scrapers.blog_scraper import BlogScraper
        from src.ingestion.scrapers.arxiv_scraper import ArxivScraper

        source_type = source["source_type"]
        name = source["source"]
        logger.info("scraper_building", source=name, source_type=source_type)

        try:
            if source_type == "rss":
                return RssScraper(url=source["url"], source=name)

            if source_type == "blog":
                return BlogScraper(
                    base_url=source["base_url"],
                    source=name,
                    selectors=source["selectors"],
                )

            if source_type == "arxiv":
                cfg = source.get("selector_config", {})
                return ArxivScraper(
                    max_results=cfg.get("max_results", 30),
                    days_back=cfg.get("days_back", 1),
                )

            logger.warning("unknown_source_type", source_type=source_type)
            return None

        except Exception as e:
            logger.error("scraper_init_failed", source=name, error=str(e))
            return None
