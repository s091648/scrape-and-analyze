from typing import List

from src.shared.logging import get_logger
from src.modules.collection.domain.entities import ScraperSetting, ScrapeJob
from src.modules.collection.domain.repositories import ScraperSettingRepository
from src.modules.collection.domain.factories import ScraperFactory

logger = get_logger(__name__)


class DiscoverScrapeJobsUseCase:
    """
    Queries all due ScraperSettings, discovers pending article URLs from each
    source, marks settings as scraped, and returns the full list of ScrapeJobs
    for infrastructure to execute.
    """

    def __init__(
        self,
        setting_repo: ScraperSettingRepository,
        scraper_factory: ScraperFactory,
    ) -> None:
        self._setting_repo = setting_repo
        self._scraper_factory = scraper_factory

    def execute(self) -> List[ScrapeJob]:
        """Query due scraper settings, discover pending URLs from each source, mark settings scraped, and return all ScrapeJobs."""
        due_settings = self._setting_repo.get_active_due()

        if not due_settings:
            logger.info("no_sources_due")
            return []

        logger.info("sources_due", count=len(due_settings))

        all_jobs: List[ScrapeJob] = []

        for setting in due_settings:
            jobs = self._discover_for(setting)
            all_jobs.extend(jobs)
            self._setting_repo.mark_scraped(setting.id)

        logger.info("scrape_jobs_discovered", total=len(all_jobs))
        return all_jobs

    def _discover_for(self, setting: ScraperSetting) -> List[ScrapeJob]:
        """Create a scraper for the given setting and discover its pending ScrapeJobs."""
        try:
            scraper = self._scraper_factory.create_for(setting)
            jobs = scraper.discover()
            logger.info("source_discovered", source=setting.source, jobs=len(jobs))
            return jobs
        except Exception as e:
            logger.error("source_discover_failed", source=setting.source, error=str(e))
            return []
