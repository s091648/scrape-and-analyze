import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, List, Optional, Tuple
from urllib.parse import urlparse

try:  # optional dependency — RAG SDK isn't always installed
    from chatbot_plugin_sdk import RateLimitExhausted
except ModuleNotFoundError:  # pragma: no cover
    class RateLimitExhausted(Exception):  # type: ignore[no-redef]
        pass

from src.infrastructure.collection.clients.arxiv_client import ARXIV_API_URL
from src.infrastructure.collection.clients.openalex_client import OPENALEX_API_URL
from src.infrastructure.collection.clients.semantic_scholar_client import SEMANTIC_SCHOLAR_API_URL
from shared.enums.observability import SpanName
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
        rag_service_aclose: Optional[Callable[[], Awaitable[None]]] = None,
        rag_dispatch_concurrency: int = 10,
        rag_ingest_timeout: float = 0.0,
        failed_task_repo_factory: Optional[Callable[[Any], Any]] = None,
        text_stage_concurrency: int = 10,
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
        # 024-async-pipeline-refactor US6: releases the RAG-ingestion SDK's
        # EmbeddingBatchCoordinator worker task (research.md item 11) — called
        # once, after Barrier 2, so it never fires while a RAG task might still
        # submit more chunks.
        self._rag_service_aclose = rag_service_aclose
        self._rag_tasks: List[asyncio.Task] = []
        # ── RAG daily-quota (RPD) circuit breaker ──────────────────────────
        # The embedding provider's RPD cap, once spent, raises RateLimitExhausted
        # on every subsequent call for the rest of the process — so once one RAG
        # task hits it, every remaining article would fail identically (and each
        # would still sit minutes in the shared embedding queue first). When this
        # flips True, no further RAG ingestion is attempted this run; the
        # untried articles are recorded in one bulk FailedTask write at run end
        # (below) and left for the RAG-backfill cron to pick up.
        self._rag_rate_limited = False
        self._rag_skipped_tasks: list = []  # list[FailedTask], bulk-written after Barrier 2
        # Backstop wall-clock cap per article's RAG ingestion (0 = disabled).
        self._rag_ingest_timeout = rag_ingest_timeout
        # Callable[[AsyncSession], AsyncFailedTaskRepository] — used only for the
        # run-end bulk write of circuit-breaker-skipped articles.
        self._failed_task_repo_factory = failed_task_repo_factory
        # Bounds how many RAG-ingesting articles concurrently hold an open
        # AsyncSession (one connection from the async engine's bounded pool, see
        # src/infrastructure/persistence/database.py) — NOT embedding-API
        # throughput (that's RAG_DENSE_RPM/RAG_EMBED_BATCH_SIZE, a separate,
        # unrelated concern). Gates entry to _run_rag_ingestion()'s body, not
        # task creation in _dispatch_rag() — a task blocked on this semaphore
        # hasn't opened a session or enqueued any chunks yet, which also caps
        # how many chunks can burst into the embedding coordinator's queue at
        # once (research.md item 11 follow-up, 024-async-pipeline-refactor US6).
        self._rag_dispatch_semaphore = asyncio.BoundedSemaphore(rag_dispatch_concurrency)
        # Bounds how many per-article text-stage tasks concurrently hold an open
        # AsyncSession (one pooled connection) + are mid-LLM chain. Barrier 1 fans
        # out one task per article at once; without this, a large run opens as
        # many cold connections as there are articles in a single burst — the
        # asyncpg connect-starvation this whole change addresses. Held only for
        # the text stage (through bus.publish()), released before the detached
        # RAG task settles — RAG has its own separate _rag_dispatch_semaphore.
        # Keep text_stage_concurrency + rag_dispatch_concurrency at or below the
        # async pool's cap (ASYNC_DB_POOL_SIZE + ASYNC_DB_MAX_OVERFLOW), minus a
        # little headroom for run-level/housekeeping sessions; a task that can't
        # get a slot just waits (bounded by pool_timeout), it isn't dropped.
        self._text_stage_semaphore = asyncio.BoundedSemaphore(text_stage_concurrency)

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

    async def _dispatch_rag(self, event, pipeline_span=None) -> Optional[asyncio.Task]:
        """Fire RAG ingestion as a detached asyncio.Task, tracked for Barrier 2
        — deliberately NOT awaited, so this article's own text-stage chain (and
        the triggering publish() call) completes without waiting on RAG (FR-002),
        and RAG failing/being slow never blocks any other article either.

        pipeline_span is that article's article.pipeline span (still current
        when this runs, inside _process_article_text's use_span block) — passed
        through so the RAG task can parent article.rag_ingest to it explicitly
        and end it once RAG settles (approach A)."""
        if self._rag_downstream_builder is None:
            return None
        task = asyncio.create_task(self._run_rag_ingestion(event, pipeline_span))
        self._rag_tasks.append(task)
        return task

    def _make_rag_dispatcher(self, pipeline_span, rag_task_box: List[asyncio.Task]):
        """Per-article ArticleProcessedEvent subscriber: delegates to
        _dispatch_rag with this article's span, and records the resulting task
        in rag_task_box — _process_article_text's signal that a RAG task now
        owns ending the article.pipeline span."""
        async def _dispatch(event) -> None:
            task = await self._dispatch_rag(event, pipeline_span)
            if task is not None:
                rag_task_box.append(task)
        return _dispatch

    async def _run_rag_ingestion(self, event, pipeline_span=None) -> None:
        """Owns its own AsyncSession for the whole task lifetime — separate
        from (and outliving) the text-stage task's session, since RAG may
        still be running after the article's text-stage task has already
        returned and closed its session. Only used for recording a
        RagIngestionFailedEvent as a FailedTask on error; RAG ingestion
        itself goes through the SDK's own, separate DB connection.

        Gated by _rag_dispatch_semaphore — a task blocked here (unbounded
        article volume vs. a bounded number of concurrent, unpooled Postgres
        connections) hasn't opened its AsyncSession yet.

        Circuit breaker: if a prior task already spent the embedding provider's
        daily quota (RateLimitExhausted), skip straight to recording a deferred
        FailedTask — don't open a session, don't enqueue chunks, don't wait.

        Ends pipeline_span (the article.pipeline span) once RAG settles, so the
        article's span time window actually contains its RAG ingestion."""
        try:
            if self._rag_rate_limited:
                self._record_rag_skipped(event)
                return
            async with self._rag_dispatch_semaphore:
                # The breaker may have tripped while this task waited its turn.
                if self._rag_rate_limited:
                    self._record_rag_skipped(event)
                    return
                async with self._async_sessionmaker_factory() as session:
                    handler = await self._rag_downstream_builder(session)
                    coro = handler.handle(event, parent_span=pipeline_span)
                    try:
                        if self._rag_ingest_timeout and self._rag_ingest_timeout > 0:
                            await asyncio.wait_for(coro, timeout=self._rag_ingest_timeout)
                        else:
                            await coro
                    except RateLimitExhausted:
                        # First article to spend the daily quota — trip the
                        # breaker so the rest of the run skips RAG. This
                        # article's own FailedTask was already written inline
                        # by the handler before it re-raised.
                        if not self._rag_rate_limited:
                            self._rag_rate_limited = True
                            logger.warning(
                                "rag_rate_limit_circuit_open",
                                url=str(getattr(event.article, "url", "")),
                            )
                    except (asyncio.TimeoutError, TimeoutError):
                        logger.error(
                            "rag_ingest_timeout",
                            url=str(getattr(event.article, "url", "")),
                            timeout_seconds=self._rag_ingest_timeout,
                        )
                        self._record_rag_skipped(
                            event,
                            reason="TimeoutError",
                            message=f"RAG ingestion exceeded {self._rag_ingest_timeout}s backstop cap",
                        )
        finally:
            if pipeline_span is not None and pipeline_span.is_recording():
                pipeline_span.end()

    def _record_rag_skipped(self, event, reason: str = "RateLimitExhausted",
                            message: Optional[str] = None) -> None:
        """Queue a FailedTask for an article whose RAG ingestion was skipped —
        the daily quota was already spent this run, or this article hit the
        per-task timeout backstop. Bulk-written once, after Barrier 2. These
        articles keep has_vectors=FALSE and get picked up by the RAG-backfill
        cron; no per-article session/commit here."""
        import uuid as _uuid
        from src.modules.collection.domain.entities import FailedTask
        from src.infrastructure.shared.logging import get_correlation_id

        article = getattr(event, "article", None)
        corr_str = get_correlation_id()
        try:
            corr_id = _uuid.UUID(corr_str) if corr_str else None
        except (ValueError, AttributeError):
            corr_id = None
        self._rag_skipped_tasks.append(FailedTask(
            task_type="rag_ingest",
            article_id=getattr(article, "id", None),
            article_url=(str(getattr(article, "url", "")) or None),
            exception_type=reason,
            exception_message=message or (
                "RAG daily request cap (RPD) already exhausted this run — skipped, "
                "deferred to RAG backfill."
            ),
            context={"deferred": True, "reason": reason},
            correlation_id=corr_id,
            failed_at=datetime.now(timezone.utc),
        ))

    async def _process_article_text(self, article: ScrapedArticle) -> None:
        """One per-article asyncio.Task: its own AsyncSession, its own fresh
        downstream event bus + repos + use cases + handlers (built by
        article_downstream_builder), publishing this one article's
        ArticleScrapedEvent and awaiting the resulting text-stage chain.

        NOTE: this span is coarser than the sync pipeline's — the previous
        per-handler span wrapping (with_span/with_span_deferred, applied at
        subscribe() time in bootstrap.py) is not yet reintegrated here, since
        handlers are now (re)constructed fresh per article rather than
        subscribed once at bootstrap time.

        approach A (fix/scraper_failure): the article.pipeline span is managed
        manually. The text stage doesn't block on RAG, but the span is only
        ended once this article's detached RAG task settles (via
        _run_rag_ingestion), so its duration and subtree actually contain
        article.rag_ingest. When no RAG task is dispatched (RAG disabled,
        dedup, or a scrape-stage failure that stops before ArticleProcessedEvent)
        this method ends the span itself.
        """
        span = None
        rag_task_box: List[asyncio.Task] = []
        try:
            # _text_stage_semaphore gates entry here — a task still waiting on it
            # has no span and no session open yet (like the RAG semaphore), so a
            # big run doesn't open one cold pooled connection per article all at
            # once. Released when this method returns (after bus.publish), which
            # is before the detached RAG task settles.
            async with self._text_stage_semaphore:
                # end_on_exit=False: the text stage doesn't wait on RAG, but the
                # span is kept open (see _run_rag_ingestion) so its duration/
                # subtree contain the RAG work. record_exception/set_status still
                # fire on a hard failure that escapes the chain.
                with get_tracer().start_as_current_span(
                    SpanName.ARTICLE_PIPELINE, end_on_exit=False,
                ) as span:
                    span.set_attribute("article.url", article.url)
                    async with self._async_sessionmaker_factory() as session:
                        bus = self._event_bus_factory()
                        dispatch_rag = self._make_rag_dispatcher(span, rag_task_box)
                        await self._article_downstream_builder(session, bus, dispatch_rag)
                        event = ArticleScrapedEvent.from_scraped_article(article)
                        await bus.publish(event)
        except BaseException:
            if span is not None and not rag_task_box and span.is_recording():
                span.end()
            raise
        if span is not None and not rag_task_box and span.is_recording():
            span.end()

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
            outcomes = await asyncio.gather(
                *(self._process_article_text(article) for article in results),
                return_exceptions=True,
            )
            failed = 0
            for article, outcome in zip(results, outcomes, strict=True):
                if isinstance(outcome, BaseException):
                    failed += 1
                    logger.error(
                        "article_task_failed",
                        url=article.url,
                        source=article.source,
                        error=str(outcome),
                        error_type=type(outcome).__name__,
                    )
            publish_span.set_attribute("articles.task_failed", failed)
        # NOTE: pipeline.publish_articles closes here, before the detached RAG
        # tasks (and the article.pipeline spans they keep open) finish — those
        # spans intentionally outlive it (approach A). scraper.run still contains
        # everything, since pipeline.run() only returns after Barrier 2.

        stats = self._pipeline_stats.get_results()
        text_execution = self._build_execution_meta(started_at, start)
        await self._event_bus.publish(TextPipelineCompletedEvent(
            stats=stats,
            execution=text_execution,
            rate_limited_hosts=tuple(self._executor.exhausted_hosts),
            rate_limited_llm_providers=self._rate_limited_llm_providers(),
            partial_failure_count=self._pipeline_stats.partial_failure_count,
        ))

        # ── Barrier 2: every RAG task also settled ───────────────────────
        if self._rag_tasks:
            rag_outcomes = await asyncio.gather(*self._rag_tasks, return_exceptions=True)
            for outcome in rag_outcomes:
                if isinstance(outcome, BaseException):
                    logger.error(
                        "rag_task_failed",
                        error=str(outcome),
                        error_type=type(outcome).__name__,
                    )

        # ── RAG circuit-breaker: one bulk write for every skipped article ──
        rag_rate_limited_skipped = 0
        if self._rag_skipped_tasks:
            rag_rate_limited_skipped = sum(
                1 for t in self._rag_skipped_tasks
                if (t.context or {}).get("reason") == "RateLimitExhausted"
            )
            logger.warning(
                "rag_ingestion_skipped_bulk",
                skipped=len(self._rag_skipped_tasks),
                rate_limited=rag_rate_limited_skipped,
            )
            if self._failed_task_repo_factory is not None:
                try:
                    async with self._async_sessionmaker_factory() as session:
                        repo = self._failed_task_repo_factory(session)
                        await repo.save_many(self._rag_skipped_tasks)
                except Exception as e:
                    logger.error("rag_skipped_bulk_save_error", error=str(e))

        if self._rag_service_aclose is not None:
            await self._rag_service_aclose()

        duration = time.time() - start
        final_stats = self._pipeline_stats.get_results()
        await self._event_bus.publish(PipelineCompletedEvent(
            stats=final_stats,
            execution=self._build_execution_meta(started_at, start),
            rate_limited_hosts=tuple(self._executor.exhausted_hosts),
            rate_limited_llm_providers=self._rate_limited_llm_providers(),
            partial_failure_count=self._pipeline_stats.partial_failure_count,
            rag_rate_limited_skipped=rag_rate_limited_skipped,
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
