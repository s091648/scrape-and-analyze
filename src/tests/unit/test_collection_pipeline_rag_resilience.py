"""fix/scraper_failure: the RAG side of the concurrent pipeline has three
failure modes that must not silently vanish from the run summary —

  1. a per-article RAG ingestion that exceeds `rag_ingest_timeout`
  2. the embedding provider's daily quota (RPD) being spent mid-run, which
     trips a circuit breaker so the rest of the run skips RAG entirely
  3. both of the above must still be reconciled against PipelineStats so
     PipelineCompletedEvent.partial_failure_count / rag_rate_limited_skipped
     are accurate

Sibling of test_collection_pipeline_rag_dispatch_concurrency.py (the
concurrency-bound side of the same _run_rag_ingestion path)."""
import asyncio
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.collection.collection_pipeline import (
    CollectionPipeline,
    RateLimitExhausted,
)
from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus
from src.modules.collection.application.use_cases import PipelineStats
from src.modules.collection.domain.value_objects import ScrapedArticle


def _make_pipeline(
    *,
    rag_downstream_builder,
    async_sessionmaker_factory,
    rag_ingest_timeout=0.0,
    pipeline_stats=None,
):
    return CollectionPipeline(
        setting_repo=MagicMock(),
        scraper_factory=MagicMock(),
        event_bus=AsyncMock(),
        pipeline_stats=pipeline_stats or PipelineStats(),
        async_sessionmaker_factory=async_sessionmaker_factory,
        article_downstream_builder=AsyncMock(),
        rag_downstream_builder=rag_downstream_builder,
        event_bus_factory=MagicMock(),
        rag_ingest_timeout=rag_ingest_timeout,
    )


def _event(url="https://example.com/a"):
    ev = MagicMock()
    ev.article = MagicMock()
    ev.article.id = uuid.uuid4()
    ev.article.url = url
    return ev


@asynccontextmanager
async def _fake_session():
    yield MagicMock()


@pytest.mark.asyncio
async def test_rag_ingest_timeout_is_recorded_as_partial_failure_and_deferred_task():
    """A RAG ingestion that runs past the backstop cap must (a) bump the run's
    partial-failure count for that article and (b) queue a deferred FailedTask —
    otherwise PipelineCompletedEvent reports zero problems for an article whose
    vectors never landed."""
    async def _slow_handle(event, parent_span=None):
        await asyncio.sleep(0.2)

    async def _builder(session):
        handler = MagicMock()
        handler.handle = _slow_handle
        return handler

    stats = PipelineStats()
    pipeline = _make_pipeline(
        rag_downstream_builder=_builder,
        async_sessionmaker_factory=_fake_session,
        rag_ingest_timeout=0.01,
        pipeline_stats=stats,
    )
    event = _event()

    await pipeline._run_rag_ingestion(event)

    assert stats.partial_failure_count == 1
    assert len(pipeline._rag_skipped_tasks) == 1
    task = pipeline._rag_skipped_tasks[0]
    assert task.exception_type == "TimeoutError"
    assert task.article_id == event.article.id
    assert task.context == {"deferred": True, "reason": "TimeoutError"}


@pytest.mark.asyncio
async def test_first_rate_limit_trips_breaker_and_later_articles_skip_without_a_session():
    """An untyped RateLimitExhausted (dimension "unknown") is treated
    conservatively like a daily cap: it trips the breaker, so after the first
    hit no further RAG ingestion even opens a session; the untried article is
    queued for the backfill cron."""
    sessions_opened = 0

    @asynccontextmanager
    async def _counting_session():
        nonlocal sessions_opened
        sessions_opened += 1
        yield MagicMock()

    async def _rate_limited_handle(event, parent_span=None):
        raise RateLimitExhausted("daily cap")

    async def _builder(session):
        handler = MagicMock()
        handler.handle = _rate_limited_handle
        return handler

    pipeline = _make_pipeline(
        rag_downstream_builder=_builder,
        async_sessionmaker_factory=_counting_session,
    )

    # First article spends the quota → breaker trips (its own FailedTask is
    # written inline by the handler, so nothing is queued here yet).
    await pipeline._run_rag_ingestion(_event("https://example.com/1"))
    assert pipeline._rag_rate_limited is True
    assert sessions_opened == 1
    assert pipeline._rag_skipped_tasks == []

    # Second article: breaker already open → skipped, no session opened.
    await pipeline._run_rag_ingestion(_event("https://example.com/2"))
    assert sessions_opened == 1
    assert len(pipeline._rag_skipped_tasks) == 1
    assert pipeline._rag_skipped_tasks[0].exception_type == "RateLimitExhausted"


@pytest.mark.asyncio
async def test_rpd_dimension_trips_the_breaker():
    """A typed daily-cap error (dimension="rpd") opens the breaker — every
    remaining article this run would fail identically."""
    class _RpdExhausted(RateLimitExhausted):
        dimension = "rpd"

    async def _handle(event, parent_span=None):
        raise _RpdExhausted("daily cap")

    async def _builder(session):
        h = MagicMock()
        h.handle = _handle
        return h

    pipeline = _make_pipeline(
        rag_downstream_builder=_builder,
        async_sessionmaker_factory=_fake_session,
    )

    await pipeline._run_rag_ingestion(_event())

    assert pipeline._rag_rate_limited is True


@pytest.mark.asyncio
async def test_transient_rpm_dimension_does_not_trip_the_breaker():
    """A per-minute cap (dimension="rpm") recovers within the run — it must fail
    only its own article (recorded inline by the handler), never open the
    breaker that would skip RAG for every remaining article."""
    class _RpmExhausted(RateLimitExhausted):
        dimension = "rpm"

    async def _handle(event, parent_span=None):
        raise _RpmExhausted("per-minute cap")

    async def _builder(session):
        h = MagicMock()
        h.handle = _handle
        return h

    pipeline = _make_pipeline(
        rag_downstream_builder=_builder,
        async_sessionmaker_factory=_fake_session,
    )

    await pipeline._run_rag_ingestion(_event("https://example.com/rpm"))
    await pipeline._run_rag_ingestion(_event("https://example.com/rpm2"))

    assert pipeline._rag_rate_limited is False
    # Not a circuit-breaker skip — the handler's own RagIngestionFailedEvent
    # path (stubbed out here) owns recording the per-article failure.
    assert pipeline._rag_skipped_tasks == []


@pytest.mark.asyncio
async def test_circuit_broken_article_emits_a_failed_rag_span():
    """B (fix/scraper_failure): once the breaker is open, later articles never
    reach AsyncRagIngestionHandler (where article.rag_ingest is normally
    created), so _record_rag_skipped emits a short ERROR span itself — otherwise
    the article row renders as a clean ✓ despite its vectors never landing."""
    import src.infrastructure.collection.collection_pipeline as mod

    ended_spans = []

    class _SkipSpan:
        def __init__(self, name):
            self.name = name
            self.attrs = {}
            self.status = None

        def set_attribute(self, k, v):
            self.attrs[k] = v

        def set_status(self, code, desc=None):
            self.status = (code, desc)

        def end(self):
            ended_spans.append(self)

    tracer = MagicMock()
    tracer.start_span.side_effect = lambda name, **_kw: _SkipSpan(name)

    pipeline = _make_pipeline(
        rag_downstream_builder=AsyncMock(),
        async_sessionmaker_factory=_fake_session,
    )
    pipeline._rag_rate_limited = True  # breaker already open

    parent = MagicMock()
    latch = mod._ArticleSpanLatch(parent)

    original = mod.get_tracer
    mod.get_tracer = lambda: tracer
    try:
        await pipeline._run_rag_ingestion(_event("https://example.com/skip"), latch)
    finally:
        mod.get_tracer = original

    assert len(ended_spans) == 1
    span = ended_spans[0]
    assert span.name == "article.rag_ingest"
    assert span.attrs["rag_ingest.skipped"] is True
    assert span.attrs["rag_ingest.success"] is False
    assert span.status is not None and span.status[0] is not None
    # still also queued for the backfill cron
    assert len(pipeline._rag_skipped_tasks) == 1


@pytest.mark.asyncio
async def test_record_rag_skipped_builds_a_deferred_failed_task():
    pipeline = _make_pipeline(
        rag_downstream_builder=AsyncMock(),
        async_sessionmaker_factory=_fake_session,
    )
    event = _event("https://example.com/z")

    pipeline._record_rag_skipped(event)

    assert len(pipeline._rag_skipped_tasks) == 1
    task = pipeline._rag_skipped_tasks[0]
    assert task.task_type == "rag_ingest"
    assert task.article_id == event.article.id
    assert task.article_url == "https://example.com/z"
    assert task.exception_type == "RateLimitExhausted"
    assert task.context == {"deferred": True, "reason": "RateLimitExhausted"}


@pytest.mark.asyncio
async def test_rag_ingestion_within_timeout_records_nothing():
    """Guard against a regression that flags every RAG run as a partial failure:
    a handler that finishes before the cap must leave stats and the deferred
    queue untouched."""
    async def _fast_handle(event, parent_span=None):
        return None

    async def _builder(session):
        handler = MagicMock()
        handler.handle = _fast_handle
        return handler

    stats = PipelineStats()
    pipeline = _make_pipeline(
        rag_downstream_builder=_builder,
        async_sessionmaker_factory=_fake_session,
        rag_ingest_timeout=5.0,
        pipeline_stats=stats,
    )

    await pipeline._run_rag_ingestion(_event())

    assert stats.partial_failure_count == 0
    assert pipeline._rag_skipped_tasks == []


@pytest.mark.asyncio
async def test_make_rag_dispatcher_records_the_task_in_the_box_for_the_text_stage():
    """_make_rag_dispatcher is the per-article ArticleProcessedEvent subscriber:
    it fires the detached RAG task via _dispatch_rag and drops it into
    rag_task_box — _process_article_text's signal that a RAG task now owns
    ending the article.pipeline span (so the text stage must NOT end it)."""
    async def _handle(event, parent_span=None):
        return None

    async def _builder(session):
        handler = MagicMock()
        handler.handle = _handle
        return handler

    pipeline = _make_pipeline(
        rag_downstream_builder=_builder,
        async_sessionmaker_factory=_fake_session,
    )

    box: list = []
    dispatch = pipeline._make_rag_dispatcher(span_latch=MagicMock(), rag_task_box=box)
    await dispatch(_event())

    assert len(box) == 1
    assert box[0] in pipeline._rag_tasks
    await asyncio.gather(*pipeline._rag_tasks)


@pytest.mark.asyncio
async def test_make_rag_dispatcher_records_nothing_when_rag_is_disabled():
    pipeline = _make_pipeline(
        rag_downstream_builder=None,
        async_sessionmaker_factory=_fake_session,
    )
    box: list = []
    dispatch = pipeline._make_rag_dispatcher(span_latch=MagicMock(), rag_task_box=box)
    await dispatch(_event())
    assert box == []


@pytest.mark.asyncio
async def test_process_article_text_keeps_pipeline_span_open_until_rag_settles():
    """approach A: the text stage doesn't block on RAG, but the article.pipeline
    span is only ended once BOTH the text stage and the detached RAG task have
    settled (via _ArticleSpanLatch) — so its duration and subtree actually
    contain article.rag_ingest. When a RAG task IS dispatched, _process_article_text
    only marks the text side of the latch; _run_rag_ingestion's finally marks the
    RAG side, and whichever is second ends the span."""
    ended: list = []

    def _fake_span_factory():
        span = MagicMock()
        span.is_recording.return_value = True
        span.end.side_effect = lambda: ended.append(True)
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=span)
        cm.__exit__ = MagicMock(return_value=False)
        return span, cm

    span, cm = _fake_span_factory()

    async def _rag_handle(event, parent_span=None):
        return None

    async def _rag_builder(session):
        h = MagicMock()
        h.handle = _rag_handle
        return h

    async def _article_builder(session, bus, dispatch_rag):
        # Simulate ArticleProcessedHandler firing the RAG dispatcher.
        await dispatch_rag(_event())

    pipeline = CollectionPipeline(
        setting_repo=MagicMock(),
        scraper_factory=MagicMock(),
        event_bus=AsyncMock(),
        pipeline_stats=PipelineStats(),
        async_sessionmaker_factory=_fake_session,
        article_downstream_builder=_article_builder,
        rag_downstream_builder=_rag_builder,
        event_bus_factory=AsyncInMemoryEventBus,
    )

    import src.infrastructure.collection.collection_pipeline as mod
    tracer = MagicMock()
    tracer.start_as_current_span.return_value = cm
    original = mod.get_tracer
    mod.get_tracer = lambda: tracer
    try:
        article = ScrapedArticle(title="A", url="https://example.com/a", source="test",
                                 content="c", published_at=None)
        await pipeline._process_article_text(article)
        # Text side marked; RAG task hasn't settled → latch keeps the span open.
        assert ended == []
        assert len(pipeline._rag_tasks) == 1
        await asyncio.gather(*pipeline._rag_tasks)
        # RAG side marked second → latch ended the span.
        assert ended == [True]
    finally:
        mod.get_tracer = original


@pytest.mark.asyncio
async def test_rag_skipped_tasks_are_bulk_written_via_the_failed_task_repo_factory_at_run_end():
    """The circuit-breaker-skipped articles are persisted in ONE bulk write
    after Barrier 2 — not a per-article commit — using failed_task_repo_factory."""
    saved_batches: list = []

    class _Repo:
        def __init__(self, session):
            self._session = session

        async def save_many(self, tasks):
            saved_batches.append(list(tasks))

    async def _rate_limited_handle(event, parent_span=None):
        raise RateLimitExhausted("daily cap")

    async def _rag_builder(session):
        h = MagicMock()
        h.handle = _rate_limited_handle
        return h

    articles = [
        ScrapedArticle(title=f"A{i}", url=f"https://example.com/{i}", source="test",
                       content=f"c{i}", published_at=None)
        for i in range(3)
    ]

    async def _article_builder(session, bus, dispatch_rag):
        # Directly drive a RAG dispatch per article (stand-in for
        # ArticleProcessedHandler on the per-article bus).
        await dispatch_rag(_event("https://example.com/x"))

    setting = MagicMock(id="id-1", source_type="rss", url="https://example.com/feed")
    setting_repo = MagicMock()
    setting_repo.get_active_due.return_value = [setting]

    executor = MagicMock()
    executor.exhausted_hosts = []
    executor.run_discover.return_value = [MagicMock() for _ in articles]

    def _fetch_all(fetch_tasks, on_result):
        for a in articles:
            on_result(a)
    executor.run_fetch_only.side_effect = _fetch_all

    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=MagicMock(),
        event_bus=AsyncMock(),
        pipeline_stats=PipelineStats(),
        async_sessionmaker_factory=_fake_session,
        article_downstream_builder=_article_builder,
        rag_downstream_builder=_rag_builder,
        event_bus_factory=AsyncInMemoryEventBus,
        executor=executor,
        article_repo=None,
        failed_task_repo_factory=lambda session: _Repo(session),
    )

    await pipeline.run()

    # First article trips the breaker (its own FailedTask is written inline by
    # the handler); the remaining two are queued and bulk-written once.
    assert len(saved_batches) == 1
    assert len(saved_batches[0]) >= 1
    assert all(t.task_type == "rag_ingest" for t in saved_batches[0])
