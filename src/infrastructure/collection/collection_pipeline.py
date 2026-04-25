import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from src.infrastructure.collection.executor import FetchTask, ScrapeExecutor
from src.infrastructure.collection.scrapers import ConcreteScraperFactory
from src.shared.logging import get_logger
from src.modules.collection.domain.repositories import ScraperSettingRepository
from src.modules.collection.domain.value_objects import ScrapedArticle
from src.modules.collection.application.dtos import ScrapedArticleDTO
from src.modules.collection.application.use_cases import PipelineStats
from src.modules.collection.application.events.pipeline_completed import PipelineCompletedEvent
from src.shared.application.ports import EventBus

logger = get_logger(__name__)


class CollectionPipeline:
    def __init__(
        self,
        setting_repo: ScraperSettingRepository,
        scraper_factory: ConcreteScraperFactory,
        event_bus: EventBus,
        pipeline_stats: PipelineStats,
        executor: Optional[ScrapeExecutor] = None,
    ) -> None:
        self._setting_repo = setting_repo
        self._scraper_factory = scraper_factory
        self._event_bus = event_bus
        self._pipeline_stats = pipeline_stats
        self._executor = executor or ScrapeExecutor()

    def run(self) -> int:
        start = time.time()
        due_settings = self._setting_repo.get_active_due()

        if not due_settings:
            logger.info("no_sources_due")
            self._event_bus.publish(PipelineCompletedEvent(
                stats=[],
                duration_seconds=time.time() - start,
            ))
            return 0

        logger.info("sources_due", count=len(due_settings))

        # ── Phase 1: concurrent discover ──────────────────────────────────
        tasks: List[FetchTask] = []
        scraped_setting_ids = []

        def _discover(setting):
            scraper = self._scraper_factory.create_for(setting)
            return scraper, scraper.discover()

        with ThreadPoolExecutor(max_workers=len(due_settings)) as pool:
            futures = {pool.submit(_discover, s): s for s in due_settings}
            for future in as_completed(futures):
                setting = futures[future]
                try:
                    scraper, jobs = future.result()
                except Exception as e:
                    logger.error("discover_failed", source=setting.source, error=str(e))
                    continue

                logger.info("jobs_discovered", source=setting.source, count=len(jobs))
                for job in jobs:
                    tasks.append(FetchTask(
                        url=job.url,
                        source=setting.source,
                        job=job,
                        scraper=scraper,
                    ))
                scraped_setting_ids.append(setting.id)

        # ── Phase 2: concurrent fetch ─────────────────────────────────────
        results: List[ScrapedArticle] = []

        def on_result(article: ScrapedArticle) -> None:
            results.append(article)

        self._executor.run(tasks, on_result=on_result)

        # ── Phase 3: publish DTOs to event bus (triggers ArticleScrapedHandler) ─
        published = 0
        for article in results:
            dto = ScrapedArticleDTO.from_scraped_article(article)
            self._event_bus.publish(dto)
            published += 1

        # ── Mark settings scraped ─────────────────────────────────────────
        for setting_id in scraped_setting_ids:
            try:
                self._setting_repo.mark_scraped(setting_id)
            except Exception as e:
                logger.error("mark_scraped_failed", setting_id=str(setting_id), error=str(e))

        # ── Publish completion event (triggers Telegram + OTel) ───────────
        duration = time.time() - start
        self._event_bus.publish(PipelineCompletedEvent(
            stats=self._pipeline_stats.get_results(),
            duration_seconds=duration,
        ))

        logger.info("collection_pipeline_completed", published=published)
        return published