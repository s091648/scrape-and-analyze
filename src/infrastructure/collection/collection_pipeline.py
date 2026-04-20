from src.shared.logging import get_logger
from src.modules.collection.domain.repositories import ScraperSettingRepository
from src.infrastructure.collection.scrapers.scraper_factory import ConcreteScraperFactory
from src.shared.application.ports import EventBus

logger = get_logger(__name__)


class CollectionPipeline:
    """
    Infrastructure-level pipeline orchestrator.

    責任：
    1. 從 repository 取出到期的 ScraperSetting
    2. 為每個 setting 建立對應的 scraper，執行 discover()
    3. 對每筆 ScrapeJob 呼叫 scraper.fetch()，取得文章內容
    4. 將 ArticleScrapedEvent 發佈到 EventBus，觸發後續處理流程
    5. 標記 setting 已抓取（更新 last_scraped_at）

    注意：此類屬於 infrastructure layer，因此可直接依賴 ConcreteScraperFactory
    與 SQLAlchemy session — 不屬於 application use case。
    """

    def __init__(
        self,
        setting_repo: ScraperSettingRepository,
        scraper_factory: ConcreteScraperFactory,
        event_bus: EventBus,
    ) -> None:
        self._setting_repo = setting_repo
        self._scraper_factory = scraper_factory
        self._event_bus = event_bus

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
        published = 0

        for setting in due_settings:
            published += self._run_for_setting(setting)
            self._setting_repo.mark_scraped(setting.id)

        logger.info("collection_pipeline_completed", published=published)
        return published

    def _run_for_setting(self, setting) -> int:
        try:
            scraper = self._scraper_factory.create_for(setting)
            jobs = scraper.discover()
        except Exception as e:
            logger.error("discover_failed", source=setting.source, error=str(e))
            return 0

        logger.info("jobs_discovered", source=setting.source, count=len(jobs))
        published = 0

        for job in jobs:
            try:
                event = scraper.fetch(job)
                if event is None:
                    logger.warning("fetch_returned_none", url=job.url)
                    continue
                self._event_bus.publish(event)
                published += 1
            except Exception as e:
                logger.error("fetch_failed", url=job.url, error=str(e))

        return published
