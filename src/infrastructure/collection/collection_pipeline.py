from typing import List, Optional

from src.infrastructure.collection.executor import FetchTask, ScrapeExecutor
from src.infrastructure.collection.scrapers import ConcreteScraperFactory
from src.shared.logging import get_logger
from src.modules.collection.application.events import ArticleScrapedEvent
from src.modules.collection.domain.repositories import ScraperSettingRepository
from src.shared.application.ports import EventBus

logger = get_logger(__name__)


class CollectionPipeline:
    """
    Infrastructure-level pipeline orchestrator.

    責任：
    1. 從 repository 取出到期的 ScraperSetting
    2. 為每個 setting 建立對應的 scraper，執行 discover() 取得 ScrapeJob 列表
    3. 將每個 (job, scraper) 包裝成 FetchTask，交給 ScrapeExecutor
    4. ScrapeExecutor 在 Phase 2 以多線程 + per-host BoundedSemaphore 並發抓取
    5. 每筆抓取結果以 ArticleScrapedEvent 發佈到 EventBus，觸發後續處理流程
    6. 標記 setting 已抓取（更新 last_scraped_at）

    注意：此類屬於 infrastructure layer，因此可直接依賴 ConcreteScraperFactory
    與 ScrapeExecutor — 不屬於 application use case。
    """

    def __init__(
        self,
        setting_repo: ScraperSettingRepository,
        scraper_factory: ConcreteScraperFactory,
        event_bus: EventBus,
        executor: Optional[ScrapeExecutor] = None,
    ) -> None:
        self._setting_repo = setting_repo
        self._scraper_factory = scraper_factory
        self._event_bus = event_bus
        self._executor = executor or ScrapeExecutor()

    def run(self) -> int:
        """
        執行一輪完整的 collection pipeline。
        回傳：成功發佈的 ArticleScrapedEvent 數量。
        """
        due_settings = self._setting_repo.get_active_due()

        if not due_settings:
            logger.info("no_sources_due")
            return 0

        logger.info("sources_due", count=len(due_settings))

        # ── Phase 1: discover all jobs across every due setting ───────────
        tasks: List[FetchTask] = []
        scraped_setting_ids = []

        for setting in due_settings:
            try:
                scraper = self._scraper_factory.create_for(setting)
                jobs = scraper.discover()
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

        # ── Phase 2: concurrent fetch via ScrapeExecutor ──────────────────
        published = 0

        def on_result(event: ArticleScrapedEvent) -> None:
            nonlocal published
            self._event_bus.publish(event)
            published += 1

        self._executor.run(tasks, on_result=on_result)

        # ── Mark settings as scraped after all tasks complete ─────────────
        for setting_id in scraped_setting_ids:
            try:
                self._setting_repo.mark_scraped(setting_id)
            except Exception as e:
                logger.error("mark_scraped_failed", setting_id=str(setting_id), error=str(e))

        logger.info("collection_pipeline_completed", published=published)
        return published
