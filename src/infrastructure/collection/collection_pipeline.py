import time
from typing import List, Optional
from urllib.parse import urlparse

from src.infrastructure.collection.executor import DiscoverTask, ScrapeExecutor
from src.infrastructure.collection.scrapers import ConcreteScraperFactory
from src.shared.logging import get_logger
from src.modules.collection.domain.repositories import ScraperSettingRepository
from src.modules.collection.domain.value_objects import ScrapedArticle, UrlHash
from src.modules.collection.application.events import ArticleScrapedEvent, PipelineCompletedEvent
from src.modules.collection.application.use_cases import PipelineStats, ArticleOutcome
from src.shared.application.ports import EventBus
from src.shared.domain.repositories import ArticleRepository

logger = get_logger(__name__)


def _extract_host(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc if netloc else url
    except Exception:
        return url


class CollectionPipeline:
    def __init__(
        self,
        setting_repo: ScraperSettingRepository,
        scraper_factory: ConcreteScraperFactory,
        event_bus: EventBus,
        pipeline_stats: PipelineStats,
        executor: Optional[ScrapeExecutor] = None,
        article_repo: Optional[ArticleRepository] = None,
    ) -> None:
        self._setting_repo = setting_repo
        self._scraper_factory = scraper_factory
        self._event_bus = event_bus
        self._pipeline_stats = pipeline_stats
        self._executor = executor or ScrapeExecutor()
        self._article_repo = article_repo

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

        # ── Build discover tasks ────────────────────────────────────────
        discover_tasks: List[DiscoverTask] = []
        scraped_setting_ids = []

        for setting in due_settings:
            scraper = self._scraper_factory.create_for(setting)
            # arXiv settings store no meaningful URL; use the API host directly
            # so the discover cooldown in ScrapeExecutor is applied correctly.
            host = "export.arxiv.org" if setting.source_type == "arxiv" else _extract_host(setting.url)
            discover_tasks.append(DiscoverTask(
                setting=setting,
                scraper=scraper,
                host=host,
            ))
            scraped_setting_ids.append(setting.id)

        # ── Streaming discover + fetch ──────────────────────────────────
        results: List[ScrapedArticle] = []

        def on_result(article: ScrapedArticle) -> None:
            results.append(article)

        self._executor.run_streaming(
            discover_tasks=discover_tasks,
            on_result=on_result,
        )

        # ── Pre-dedup: filter URLs already fully processed ──────────────
        if results:
            url_hashes: dict[str, ScrapedArticle] = {}
            for a in results:
                h = UrlHash.from_url(a.url).value
                if h in url_hashes:
                    self._pipeline_stats.record(a.source, ArticleOutcome.DUPLICATE)
                else:
                    url_hashes[h] = a
            results = list(url_hashes.values())

            if self._article_repo is not None:
                analyzed = self._article_repo.find_analyzed_url_hashes(set(url_hashes.keys()))
                if analyzed:
                    kept, skipped = [], []
                    for h, a in url_hashes.items():
                        (skipped if h in analyzed else kept).append(a)
                    for a in skipped:
                        self._pipeline_stats.record(a.source, ArticleOutcome.DUPLICATE)
                    results = kept
                    logger.info(
                        "post_dedup_filtered",
                        skipped=len(skipped),
                        remaining=len(results),
                    )

        # ── Publish events to event bus (triggers ArticleScrapedHandler) ─
        published = 0
        for article in results:
            event = ArticleScrapedEvent.from_scraped_article(article)
            self._event_bus.publish(event)
            published += 1

        # ── Mark settings scraped ───────────────────────────────────────
        for setting_id in scraped_setting_ids:
            try:
                self._setting_repo.mark_scraped(setting_id)
            except Exception as e:
                logger.error("mark_scraped_failed", setting_id=str(setting_id), error=str(e))

        # ── Publish completion event (triggers Telegram + OTel) ────────
        duration = time.time() - start
        self._event_bus.publish(PipelineCompletedEvent(
            stats=self._pipeline_stats.get_results(),
            duration_seconds=duration,
        ))

        logger.info("collection_pipeline_completed", published=published)
        return published
