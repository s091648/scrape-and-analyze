"""
RunScraperUseCase — top-level orchestration for a single scrape run.

Extracted from main.py:main() + run_scrape_cycle().
Depends only on domain interfaces + ScraperService; no ORM, no session.

Session strategy: process_uc_factory is called once per scraped article,
returning a (ProcessArticleUseCase, session) pair.  The caller (composition
root) injects the factory; this use case never touches SQLAlchemy directly.
"""
from typing import Any, Callable, Tuple

from src.app.use_cases.process_article import ProcessArticleUseCase
from src.domain.repositories.scraper_setting_repository import ScraperSettingRepository
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RunScraperUseCase:

    def __init__(
        self,
        scraper_setting_repo: ScraperSettingRepository,
        scraper_service,          # ingestion.services.scraper_service.ScraperService
        process_uc_factory: Callable[[], Tuple[ProcessArticleUseCase, Any]],
        prompt: str,
    ) -> None:
        self._setting_repo = scraper_setting_repo
        self._scraper_svc = scraper_service
        self._process_uc_factory = process_uc_factory
        self._prompt = prompt

    def execute(self, correlation_id: str, summary=None) -> None:
        """
        Discover sources due for scraping, run them, and mark each as scraped.

        For each scraped article the factory is called to obtain a fresh
        (ProcessArticleUseCase, session) pair; the session is closed when the
        article's pipeline completes, regardless of success or failure.

        Args:
            correlation_id: UUID string for the current run (for tracing/logging).
            summary:        Optional RunSummary for aggregated stats.
        """
        sources = self._setting_repo.get_sources_due()
        if not sources:
            logger.info("no_sources_due")
            return

        logger.info("sources_due", count=len(sources))

        def on_result(scraped) -> None:
            process_uc, session = self._process_uc_factory()
            try:
                process_uc.execute(scraped, self._prompt, correlation_id, summary)
            finally:
                session.close()

        completed_sources = self._scraper_svc.run(sources, on_result)

        for source in completed_sources:
            try:
                self._setting_repo.mark_scraped(source["id"])
            except Exception as e:
                logger.warning("mark_scraped_failed", source_id=source["id"], error=str(e))
