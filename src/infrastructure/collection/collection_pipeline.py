import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, List, Optional, Tuple
from urllib.parse import urlparse

from src.infrastructure.collection.clients.arxiv_client import ARXIV_API_URL
from src.infrastructure.collection.clients.openalex_client import OPENALEX_API_URL
from src.infrastructure.collection.clients.semantic_scholar_client import SEMANTIC_SCHOLAR_API_URL
from src.infrastructure.collection.executor import DiscoverTask, ScrapeExecutor
from src.infrastructure.collection.scrapers import ConcreteScraperFactory
from src.infrastructure.shared.observability import get_tracer
from src.shared.logging import get_logger
from src.modules.collection.domain.repositories import ScraperSettingRepository
from src.modules.collection.domain.value_objects import ScrapedArticle, UrlHash
from src.modules.collection.application.events import (
    ArticleScrapedEvent, PipelineCompletedEvent, TextPipelineCompletedEvent,
)
from src.modules.collection.application.use_cases import PipelineStats, ArticleOutcome
from src.shared.domain.repositories import ArticleRepository
from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta

logger = get_logger(__name__)


def _extract_host(url: str) -> str:
    """Return the network location (host) from a URL, falling back to the raw string."""
    try:
        netloc = urlparse(url).netloc
        return netloc if netloc else url
    except Exception:
        return url


# ScraperSetting.url is not a usable host source for these three source_types —
# they don't scrape "a URL" at all, they call a fixed API client whose target
# host is a constant of that client (ArxivScraper.discover() never even reads
# setting.url). Derived from each client's own URL constant (not duplicated as
# a bare string) so this stays correct if a client's API host ever changes.
_SOURCE_TYPE_HOST_OVERRIDES = {
    "arxiv": _extract_host(ARXIV_API_URL),
    "semantic_scholar": _extract_host(SEMANTIC_SCHOLAR_API_URL),
    "openalex": _extract_host(OPENALEX_API_URL),
}


class CollectionPipeline:
    """Orchestrates the full discover-fetch-dedup-publish cycle for due scraper sources.

    024-async-pipeline-refactor: `run()` is now `async def`. Discover/fetch
    (unchanged, still batched — FR-003) run via `asyncio.to_thread` so the
    long blocking ScrapeExecutor calls don't hold up the event loop; the
    batched dedup DB lookups stay direct sync calls (fast, one-time). From
    the publish point onward, each article gets its own `asyncio.Task` with
    its own `AsyncSession` (research.md item 2) — RAG ingestion is dispatched
    as a further detached task per article (item 5) so it never blocks that
    article's own text-stage completion or any other article's progress.
    Two barriers replace the old single completion event (data-model.md):
    Barrier 1 (`TextPipelineCompletedEvent`) once every article's text stage
    has settled; Barrier 2 (`PipelineCompletedEvent`, unchanged semantics)
    once every article's RAG task has also settled.
    """
    def __init__(
        self,
        setting_repo: ScraperSettingRepository,
        scraper_factory: ConcreteScraperFactory,
        event_bus: Any,
        pipeline_stats: PipelineStats,
        async_sessionmaker_factory: Callable[[], Any],
        article_downstream_builder: Callable[..., Awaitable[None]],
        rag_downstream_builder: Optional[Callable[..., Awaitable[Any]]],
        event_bus_factory: Callable[[], Any],
        executor: Optional[ScrapeExecutor] = None,
        article_repo: Optional[ArticleRepository] = None,
        app_env: str = "unknown",
        jitter_seconds: Optional[float] = None,
        llm_service: Optional[Any] = None,
    ) -> None:
        self._setting_repo = setting_repo
        self._scraper_factory = scraper_factory
        # Run-level bus: only the two barrier events (TextPipelineCompletedEvent,
        # PipelineCompletedEvent) are published here — never per-article events,
        # which each get their own fresh bus (built by article_downstream_builder)
        # bound to that article's own AsyncSession.
        self._event_bus = event_bus
        self._pipeline_stats = pipeline_stats
        self._async_sessionmaker_factory = async_sessionmaker_factory
        self._article_downstream_builder = article_downstream_builder
        self._rag_downstream_builder = rag_downstream_builder
        # 024-async-pipeline-refactor US5: injected rather than importing
        # AsyncInMemoryEventBus directly here — keeps this module dependent
        # only on the EventBus Protocol, so a future Redis Streams-backed bus
        # is a drop-in swap for the per-article bus too, not just the
        # run-level one (see contracts/event-bus-port.md, T065).
        self._event_bus_factory = event_bus_factory
        self._executor = executor or ScrapeExecutor()
        self._article_repo = article_repo
        self._app_env = app_env
        self._jitter_seconds = jitter_seconds
        self._llm_service = llm_service
        self._rag_tasks: List[asyncio.Task] = []

    def _build_execution_meta(self, started_at: datetime, start: float) -> JobExecutionMeta:
        return JobExecutionMeta(
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=time.time() - start,
            app_env=self._app_env,
            jitter_seconds=self._jitter_seconds,
        )

    def _rate_limited_llm_providers(self) -> Tuple[str, ...]:
        """LLM provider names that hit RateLimitExhausted this run, if the
        pipeline was given the same AsyncResilientLLMService instance the
        analyze/translate use cases share — empty tuple if not wired or none
        hit it."""
        if self._llm_service is None:
            return ()
        return tuple(getattr(self._llm_service, "exhausted_providers", []))

    # ── Per-article downstream (concurrent) ─────────────────────────────────

    async def _dispatch_rag(self, event) -> None:
        """Subscribed to ArticleProcessedEvent on each article's own bus.
        Fires RAG ingestion as a detached asyncio.Task, tracked for Barrier 2
        — deliberately NOT awaited here, so this article's own text-stage
        chain (and the triggering publish() call) completes without waiting
        on RAG (FR-002), and RAG failing/being slow never blocks any other
        article either."""
        if self._rag_downstream_builder is None:
            return
        task = asyncio.create_task(self._run_rag_ingestion(event))
        self._rag_tasks.append(task)

    async def _run_rag_ingestion(self, event) -> None:
        """Owns its own AsyncSession for the whole task lifetime — separate
        from (and outliving) the text-stage task's session, since RAG may
        still be running after the article's text-stage task has already
        returned and closed its session. Only used for recording a
        RagIngestionFailedEvent as a FailedTask on error; RAG ingestion
        itself goes through the SDK's own, separate DB connection."""
        async with self._async_sessionmaker_factory() as session:
            handler = await self._rag_downstream_builder(session)
            await handler.handle(event)

    async def _process_article_text(self, article: ScrapedArticle) -> None:
        """One per-article asyncio.Task: its own AsyncSession, its own fresh
        downstream event bus + repos + use cases + handlers (built by
        article_downstream_builder), publishing this one article's
        ArticleScrapedEvent and awaiting the resulting text-stage chain.

        NOTE: this span is coarser than the sync pipeline's — the previous
        per-handler span wrapping (with_span/with_span_deferred, applied at
        subscribe() time in bootstrap.py) is not yet reintegrated here, since
        handlers are now (re)constructed fresh per article rather than
        subscribed once at bootstrap time. Individual handler spans
        (ARTICLE_SCRAPED_HANDLE, ARTICLE_PROCESSED_HANDLE, etc.) are
        currently NOT emitted as separate child spans — only this one
        article.pipeline span wraps the whole per-article chain. Restoring
        per-handler span granularity is tracked as follow-up work.
        """
        with get_tracer().start_as_current_span("article.pipeline") as span:
            span.set_attribute("article.url", article.url)
            async with self._async_sessionmaker_factory() as session:
                bus = self._event_bus_factory()
                await self._article_downstream_builder(session, bus, self._dispatch_rag)
                event = ArticleScrapedEvent.from_scraped_article(article)
                await bus.publish(event)

    async def run(self) -> int:
        """Execute the full pipeline for all due sources and return the number of articles published."""
        tracer = get_tracer()
        started_at = datetime.now(timezone.utc)
        start = time.time()
        due_settings = self._setting_repo.get_active_due()

        if not due_settings:
            logger.info("no_sources_due")
            await self._event_bus.publish(PipelineCompletedEvent(
                stats=[],
                execution=self._build_execution_meta(started_at, start),
                rate_limited_hosts=tuple(self._executor.exhausted_hosts),
                rate_limited_llm_providers=self._rate_limited_llm_providers(),
            ))
            return 0

        logger.info("sources_due", count=len(due_settings))

        # ── Mark settings scraped eagerly (before network I/O) ─────────
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
            host = _SOURCE_TYPE_HOST_OVERRIDES.get(setting.source_type) or _extract_host(setting.url)
            discover_tasks.append(DiscoverTask(
                setting=setting,
                scraper=scraper,
                host=host,
            ))

        # ── Discover phase (unchanged, batched — FR-003) ─────────────────
        # asyncio.to_thread frees the event loop for the duration of this
        # long, synchronous, multi-threaded ScrapeExecutor call — nothing
        # else is running concurrently yet at this point in the run anyway
        # (no article tasks exist until discover+fetch+dedup finish), but
        # this keeps the coroutine genuinely non-blocking rather than
        # relying on that being true.
        def _pre_fetch_filter(tasks):
            """Filter out FetchTasks whose URLs have already been analyzed."""
            hashes = {UrlHash.from_url(t.url).value: t for t in tasks}
            analyzed = self._article_repo.find_analyzed_url_hashes(set(hashes.keys()))
            if not analyzed:
                return tasks
            kept = [t for h, t in hashes.items() if h not in analyzed]
            skipped_tasks = [t for h, t in hashes.items() if h in analyzed]
            for t in skipped_tasks:
                self._pipeline_stats.record(t.source, ArticleOutcome.DUPLICATE)
                logger.info("article_duplicate_skipped", url=t.url, source=t.source)
            if skipped_tasks:
                logger.info("pre_fetch_dedup_filtered", skipped=len(skipped_tasks), remaining=len(kept))
            return kept

        pre_fetch_filter = _pre_fetch_filter if self._article_repo is not None else None

        with tracer.start_as_current_span("pipeline.discover") as discover_span:
            discover_span.set_attribute("sources.count", len(discover_tasks))
            fetch_tasks = await asyncio.to_thread(
                self._executor.run_discover,
                discover_tasks=discover_tasks,
                pre_fetch_filter=pre_fetch_filter,
            )
            discover_span.set_attribute("articles.discovered", len(fetch_tasks))

        # ── Fetch phase (unchanged, batched — FR-003) ─────────────────────
        results: List[ScrapedArticle] = []

        def on_result(article: ScrapedArticle) -> None:
            results.append(article)

        with tracer.start_as_current_span("pipeline.fetch") as fetch_span:
            fetch_span.set_attribute("articles.to_fetch", len(fetch_tasks))
            await asyncio.to_thread(
                self._executor.run_fetch_only,
                fetch_tasks=fetch_tasks,
                on_result=on_result,
            )
            fetch_span.set_attribute("articles.fetched", len(results))

        # ── Pre-dedup: filter URLs already fully processed (unchanged, batched) ──
        articles_before_dedup = len(results)
        with tracer.start_as_current_span("pipeline.dedup") as dedup_span:
            dedup_span.set_attribute("articles.before_dedup", articles_before_dedup)
            if results:
                url_hashes: dict[str, ScrapedArticle] = {}
                for a in results:
                    h = UrlHash.from_url(a.url).value
                    if h in url_hashes:
                        self._pipeline_stats.record(a.source, ArticleOutcome.DUPLICATE)
                        logger.info("article_duplicate_skipped", url=a.url, source=a.source,
                                    original_source=a.extra.get("original_source"))
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
                            logger.info("article_duplicate_skipped", url=a.url, source=a.source,
                                        original_source=a.extra.get("original_source"))
                        results = kept
                        logger.info(
                            "post_dedup_filtered",
                            skipped=len(skipped),
                            remaining=len(results),
                        )
            dedup_span.set_attribute("articles.after_dedup", len(results))
            dedup_span.set_attribute("articles.skipped", articles_before_dedup - len(results))

        # ── Barrier 1: fan out one asyncio.Task per article, gather with
        # settle semantics (research.md item 6) ─────────────────────────
        published = len(results)
        with tracer.start_as_current_span("pipeline.publish_articles") as publish_span:
            publish_span.set_attribute("articles.published", published)
            await asyncio.gather(
                *(self._process_article_text(article) for article in results),
                return_exceptions=True,
            )

        stats = self._pipeline_stats.get_results()
        text_execution = self._build_execution_meta(started_at, start)
        await self._event_bus.publish(TextPipelineCompletedEvent(
            stats=stats,
            execution=text_execution,
            rate_limited_hosts=tuple(self._executor.exhausted_hosts),
            rate_limited_llm_providers=self._rate_limited_llm_providers(),
        ))

        # ── Barrier 2: every RAG task also settled ───────────────────────
        if self._rag_tasks:
            await asyncio.gather(*self._rag_tasks, return_exceptions=True)

        duration = time.time() - start
        final_stats = self._pipeline_stats.get_results()
        await self._event_bus.publish(PipelineCompletedEvent(
            stats=final_stats,
            execution=self._build_execution_meta(started_at, start),
            rate_limited_hosts=tuple(self._executor.exhausted_hosts),
            rate_limited_llm_providers=self._rate_limited_llm_providers(),
        ))

        logger.info(
            "collection_pipeline_completed",
            published=published,
            duration_seconds=round(duration, 1),
            sources=len(final_stats),
            new=sum(s.new for s in final_stats),
            duplicate=sum(s.duplicate for s in final_stats),
            failed=sum(s.failed for s in final_stats),
        )
        return published
