import time
from typing import List, Optional
from urllib.parse import urlparse

from opentelemetry import trace as _otel
from src.infrastructure.collection.executor import DiscoverTask, ScrapeExecutor
from src.infrastructure.collection.scrapers import ConcreteScraperFactory
from src.infrastructure.shared.observability import get_tracer
from src.shared.logging import get_logger
from src.modules.collection.domain.repositories import ScraperSettingRepository
from src.modules.collection.domain.value_objects import ScrapedArticle, UrlHash
from src.modules.collection.application.events import ArticleScrapedEvent, PipelineCompletedEvent
from src.modules.collection.application.use_cases import PipelineStats, ArticleOutcome
from src.shared.application.ports import EventBus
from src.shared.domain.repositories import ArticleRepository

logger = get_logger(__name__)


def _extract_host(url: str) -> str:
    """Return the network location (host) from a URL, falling back to the raw string."""
    try:
        netloc = urlparse(url).netloc
        return netloc if netloc else url
    except Exception:
        return url


class CollectionPipeline:
    """Orchestrates the full discover-fetch-dedup-publish cycle for due scraper sources."""
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
        """Execute the full pipeline for all due sources and return the number of articles published."""
        tracer = get_tracer()
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

        # ── Mark settings scraped eagerly (before network I/O) ─────────
        # last_scraped_at records when the pipeline *committed* to scraping
        # a source, not when it finished. This prevents the tolerance window
        # from shrinking when pipeline execution is long (e.g. 35 min run +
        # 30 min tolerance = next-day check fails by 5 min).
        scraped_setting_ids = [s.id for s in due_settings]
        for setting_id in scraped_setting_ids:
            try:
                self._setting_repo.mark_scraped(setting_id)
            except Exception as e:
                logger.error("mark_scraped_failed", setting_id=str(setting_id), error=str(e))

        # ── Build discover tasks ────────────────────────────────────────
        discover_tasks: List[DiscoverTask] = []

        for setting in due_settings:
            scraper = self._scraper_factory.create_for(setting)
            # arXiv settings store no meaningful URL; use the API host directly
            # so the discover cooldown in ScrapeExecutor is applied correctly.
            if setting.source_type == "arxiv":
                host = "export.arxiv.org"
            elif setting.source_type == "semantic_scholar":
                host = "api.semanticscholar.org"
            elif setting.source_type == "openalex":
                host = "api.openalex.org"
            else:
                host = _extract_host(setting.url)
            discover_tasks.append(DiscoverTask(
                setting=setting,
                scraper=scraper,
                host=host,
            ))

        # ── Discover phase ─────────────────────────────────────────────
        def _pre_fetch_filter(tasks):
            hashes = {UrlHash.from_url(t.url).value: t for t in tasks}
            analyzed = self._article_repo.find_analyzed_url_hashes(set(hashes.keys()))
            if not analyzed:
                return tasks
            kept = [t for h, t in hashes.items() if h not in analyzed]
            skipped_tasks = [t for h, t in hashes.items() if h in analyzed]
            for t in skipped_tasks:
                self._pipeline_stats.record(t.source, ArticleOutcome.DUPLICATE)
            if skipped_tasks:
                logger.info("pre_fetch_dedup_filtered", skipped=len(skipped_tasks), remaining=len(kept))
            return kept

        pre_fetch_filter = _pre_fetch_filter if self._article_repo is not None else None

        with tracer.start_as_current_span("pipeline.discover") as discover_span:
            discover_span.set_attribute("sources.count", len(discover_tasks))
            fetch_tasks = self._executor.run_discover(
                discover_tasks=discover_tasks,
                pre_fetch_filter=pre_fetch_filter,
            )
            discover_span.set_attribute("articles.discovered", len(fetch_tasks))

        # ── Fetch phase ─────────────────────────────────────────────────
        results: List[ScrapedArticle] = []

        def on_result(article: ScrapedArticle) -> None:
            results.append(article)

        with tracer.start_as_current_span("pipeline.fetch") as fetch_span:
            fetch_span.set_attribute("articles.to_fetch", len(fetch_tasks))
            self._executor.run_fetch_only(
                fetch_tasks=fetch_tasks,
                on_result=on_result,
            )
            fetch_span.set_attribute("articles.fetched", len(results))

        # ── Pre-dedup: filter URLs already fully processed ──────────────
        articles_before_dedup = len(results)
        with tracer.start_as_current_span("pipeline.dedup") as dedup_span:
            dedup_span.set_attribute("articles.before_dedup", articles_before_dedup)
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
            dedup_span.set_attribute("articles.after_dedup", len(results))
            dedup_span.set_attribute("articles.skipped", articles_before_dedup - len(results))

        # ── Publish events to event bus (triggers ArticleScrapedHandler) ─
        published = 0
        with tracer.start_as_current_span("pipeline.publish_articles") as publish_span:
            for article in results:
                event = ArticleScrapedEvent.from_scraped_article(article)
                self._event_bus.publish(event)
                published += 1
            publish_span.set_attribute("articles.published", published)

        # ── Publish completion event (triggers Telegram + OTel) ────────
        duration = time.time() - start
        stats = self._pipeline_stats.get_results()
        self._event_bus.publish(PipelineCompletedEvent(
            stats=stats,
            duration_seconds=duration,
        ))

        logger.info(
            "collection_pipeline_completed",
            published=published,
            duration_seconds=round(duration, 1),
            sources=len(stats),
            new=sum(s.new for s in stats),
            duplicate=sum(s.duplicate for s in stats),
            failed=sum(s.failed for s in stats),
        )
        return published
