"""CollectionPipeline.run() failure / edge paths not covered by the barrier and
concurrency tests: the RAG rate-limit circuit breaker, the per-task RAG timeout
backstop, the bulk write of skipped RAG tasks (real FailedTask rows in the test
schema, via the real AsyncSqlAlchemyFailedTaskRepository), the pre-fetch and post-fetch
dedup filters, and per-article / per-translation task failures that must not abort
the run.

Downstream builders are fakes (same pattern as test_pipeline_barriers.py); the
session factory is the real test-schema async_sessionmaker so the FailedTask bulk
write actually hits Postgres."""
import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from models.failed_task import FailedTask as FailedTaskModel
from src.infrastructure.collection.collection_pipeline import CollectionPipeline, RateLimitExhausted
from src.infrastructure.persistence.shared.failed_task_async_repo_impl import AsyncSqlAlchemyFailedTaskRepository
from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus
from src.modules.collection.application.events import (
    ArticleScrapedEvent, PipelineCompletedEvent, TextPipelineCompletedEvent,
)
from src.modules.collection.application.use_cases import PipelineStats
from src.modules.collection.domain.value_objects import ScrapedArticle, UrlHash

pytestmark = pytest.mark.integration


class _RateLimited(RateLimitExhausted):
    """RateLimitExhausted tagged with the limit dimension the pipeline branches on.
    Bypasses the (optional) SDK class's own __init__ signature."""
    def __init__(self, dimension: str) -> None:
        Exception.__init__(self, f"{dimension} exhausted")
        self.dimension = dimension


def _articles(n: int, tag: str) -> list:
    return [
        ScrapedArticle(title=f"{tag}{i}", url=f"https://example.com/{tag}/{uuid.uuid4()}", source="rss",
                       content=f"content {i}")
        for i in range(n)
    ]


def _executor(articles, fetch_tasks=None):
    executor = MagicMock()
    executor.exhausted_hosts = []
    executor.run_discover.return_value = fetch_tasks if fetch_tasks is not None else [MagicMock() for _ in articles]

    def fetch_all(fetch_tasks, on_result):
        for a in articles:
            on_result(a)
    executor.run_fetch_only.side_effect = fetch_all
    return executor


def _setting_repo(n_settings: int = 1):
    repo = MagicMock()
    repo.get_active_due.return_value = [
        MagicMock(id=f"setting-{i}", source_type="rss", url="https://example.com/feed") for i in range(n_settings)
    ]
    return repo


async def _recording_bus():
    bus = AsyncInMemoryEventBus()
    published = []

    async def _record(event):
        published.append(event)
    await bus.subscribe(TextPipelineCompletedEvent, _record)
    await bus.subscribe(PipelineCompletedEvent, _record)
    return bus, published


def _rag_dispatching_builder():
    """Per-article builder that just forwards each scraped article to dispatch_rag, as a
    minimal ArticleProcessedEvent-shaped event (article.id/url is all the pipeline reads)."""
    async def builder(session, bus, dispatch_rag):
        async def _on_scraped(event):
            await dispatch_rag(SimpleNamespace(article=SimpleNamespace(id=None, url=event.url)))
        await bus.subscribe(ArticleScrapedEvent, _on_scraped)
    return builder


def _pipeline(articles, sessionmaker, event_bus, *, rag_handler=None, **kwargs):
    async def rag_builder(session):
        return rag_handler
    params = dict(
        setting_repo=_setting_repo(),
        scraper_factory=MagicMock(),
        event_bus=event_bus,
        pipeline_stats=PipelineStats(),
        async_sessionmaker_factory=sessionmaker,
        article_downstream_builder=_rag_dispatching_builder(),
        rag_downstream_builder=rag_builder if rag_handler is not None else None,
        event_bus_factory=AsyncInMemoryEventBus,
        executor=_executor(articles),
        failed_task_repo_factory=AsyncSqlAlchemyFailedTaskRepository,
    )
    params.update(kwargs)
    return CollectionPipeline(**params)


async def _failed_rows(sessionmaker, urls):
    async with sessionmaker() as session:
        return (await session.execute(
            select(FailedTaskModel).where(FailedTaskModel.article_url.in_(urls))
        )).scalars().all()


async def _delete_failed_rows(sessionmaker, urls):
    from sqlalchemy import delete
    async with sessionmaker() as session:
        await session.execute(delete(FailedTaskModel).where(FailedTaskModel.article_url.in_(urls)))
        await session.commit()


# ---------------------------------------------------------------------------
# RAG circuit breaker / timeout backstop + bulk FailedTask write
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_rag_quota_opens_breaker_and_bulk_records_skipped_articles(test_async_sessionmaker):
    articles = _articles(3, "rpd")
    urls = [a.url for a in articles]
    calls = []

    class _Handler:
        async def handle(self, event, parent_span=None):
            calls.append(event.article.url)
            raise _RateLimited("rpd")

    bus, published = await _recording_bus()
    aclose = AsyncMock()
    # One RAG task at a time, so the first failure trips the breaker before the rest run.
    pipeline = _pipeline(articles, test_async_sessionmaker, bus, rag_handler=_Handler(),
                         rag_dispatch_concurrency=1, rag_service_aclose=aclose)
    try:
        assert await pipeline.run() == 3

        assert len(calls) == 1, "once the daily cap is hit, remaining articles must not call the provider"
        completed = [e for e in published if isinstance(e, PipelineCompletedEvent)]
        assert completed[0].rag_rate_limited_skipped == 2
        aclose.assert_awaited_once()

        rows = await _failed_rows(test_async_sessionmaker, urls)
        assert len(rows) == 2
        assert {r.task_type for r in rows} == {"rag_ingest"}
        assert all(r.context == {"deferred": True, "reason": "RateLimitExhausted"} for r in rows)
    finally:
        await _delete_failed_rows(test_async_sessionmaker, urls)


@pytest.mark.asyncio
async def test_per_minute_rag_limit_fails_only_that_article(test_async_sessionmaker):
    articles = _articles(2, "rpm")
    calls = []

    class _Handler:
        async def handle(self, event, parent_span=None):
            calls.append(event.article.url)
            if len(calls) == 1:
                raise _RateLimited("rpm")

    bus, published = await _recording_bus()
    pipeline = _pipeline(articles, test_async_sessionmaker, bus, rag_handler=_Handler(), rag_dispatch_concurrency=1)

    await pipeline.run()

    assert len(calls) == 2, "an rpm/tpm limit is transient — it must not open the breaker"
    assert pipeline._rag_rate_limited is False
    assert pipeline._rag_skipped_tasks == []
    assert [e for e in published if isinstance(e, PipelineCompletedEvent)][0].rag_rate_limited_skipped == 0


@pytest.mark.asyncio
async def test_rag_timeout_backstop_records_a_deferred_failed_task(test_async_sessionmaker):
    articles = _articles(1, "timeout")
    urls = [a.url for a in articles]

    class _HangingHandler:
        async def handle(self, event, parent_span=None):
            await asyncio.sleep(5)

    bus, published = await _recording_bus()
    pipeline = _pipeline(articles, test_async_sessionmaker, bus, rag_handler=_HangingHandler(),
                         rag_ingest_timeout=0.05)
    try:
        await pipeline.run()

        completed = [e for e in published if isinstance(e, PipelineCompletedEvent)][0]
        # Recorded as a deferred FailedTask, but it isn't a rate-limit skip.
        assert completed.rag_rate_limited_skipped == 0
        rows = await _failed_rows(test_async_sessionmaker, urls)
        assert [(r.task_type, r.exception_type) for r in rows] == [("rag_ingest", "TimeoutError")]
        assert "backstop" in rows[0].exception_message
    finally:
        await _delete_failed_rows(test_async_sessionmaker, urls)


@pytest.mark.asyncio
async def test_bulk_save_failure_does_not_abort_the_run(test_async_sessionmaker):
    articles = _articles(2, "bulkfail")

    class _Handler:
        async def handle(self, event, parent_span=None):
            raise _RateLimited("rpd")

    def _broken_repo_factory(session):
        repo = MagicMock()
        repo.save_many = AsyncMock(side_effect=RuntimeError("db down"))
        return repo

    bus, published = await _recording_bus()
    pipeline = _pipeline(articles, test_async_sessionmaker, bus, rag_handler=_Handler(),
                         rag_dispatch_concurrency=1, failed_task_repo_factory=_broken_repo_factory)

    assert await pipeline.run() == 2
    assert any(isinstance(e, PipelineCompletedEvent) for e in published)


# ---------------------------------------------------------------------------
# Discover / dedup edges
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_due_sources_still_publishes_completion(test_async_sessionmaker):
    bus, published = await _recording_bus()
    setting_repo = MagicMock()
    setting_repo.get_active_due.return_value = []
    pipeline = _pipeline([], test_async_sessionmaker, bus, setting_repo=setting_repo)

    assert await pipeline.run() == 0

    assert [type(e) for e in published] == [PipelineCompletedEvent]
    assert published[0].stats == []


@pytest.mark.asyncio
async def test_mark_scraped_failure_is_logged_not_fatal(test_async_sessionmaker):
    articles = _articles(1, "markfail")
    setting_repo = _setting_repo()
    setting_repo.mark_scraped.side_effect = RuntimeError("db hiccup")
    bus, published = await _recording_bus()
    pipeline = _pipeline(articles, test_async_sessionmaker, bus, setting_repo=setting_repo)

    assert await pipeline.run() == 1
    assert any(isinstance(e, PipelineCompletedEvent) for e in published)


@pytest.mark.asyncio
async def test_pre_and_post_fetch_dedup_drop_already_analyzed_and_repeated_urls(test_async_sessionmaker):
    fresh, analyzed_late, analyzed_early = (f"https://example.com/dedup/{uuid.uuid4()}" for _ in range(3))
    analyzed_hashes = {UrlHash.from_url(analyzed_late).value, UrlHash.from_url(analyzed_early).value}

    article_repo = MagicMock()
    article_repo.find_analyzed_url_hashes.side_effect = lambda hashes: hashes & analyzed_hashes

    fetch_tasks = [SimpleNamespace(url=fresh, source="rss"), SimpleNamespace(url=analyzed_early, source="rss")]
    kept_by_pre_filter = []

    def run_discover(discover_tasks, pre_fetch_filter):
        kept_by_pre_filter.extend(t.url for t in pre_fetch_filter(fetch_tasks))
        return fetch_tasks

    fetched = [
        ScrapedArticle(title="fresh", url=fresh, source="rss", content="c"),
        ScrapedArticle(title="fresh again", url=fresh, source="rss", content="c"),  # within-batch repeat
        ScrapedArticle(title="late", url=analyzed_late, source="rss", content="c"),  # analyzed meanwhile
    ]
    executor = _executor(fetched)
    executor.run_discover.side_effect = run_discover

    seen_urls = []

    async def builder(session, bus, dispatch_rag):
        async def _on_scraped(event):
            seen_urls.append(event.url)
        await bus.subscribe(ArticleScrapedEvent, _on_scraped)

    bus, _ = await _recording_bus()
    stats = PipelineStats()
    pipeline = _pipeline([], test_async_sessionmaker, bus, executor=executor, article_repo=article_repo,
                         article_downstream_builder=builder, pipeline_stats=stats)

    assert await pipeline.run() == 1

    assert kept_by_pre_filter == [fresh]
    assert seen_urls == [fresh]
    # pre-fetch skip (analyzed_early) + within-batch repeat + post-fetch skip (analyzed_late)
    assert stats.get_results()[0].duplicate == 3


# ---------------------------------------------------------------------------
# Per-article / per-translation task failures are isolated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_one_article_task_crashing_does_not_stop_the_others(test_async_sessionmaker):
    articles = _articles(3, "crash")
    processed = []
    builder_calls = []

    async def builder(session, bus, dispatch_rag):
        # Raised from the builder itself (a handler's exception would be swallowed by the
        # bus) so it escapes _process_article_text — the second article's task crashes.
        # text_stage_concurrency=1 makes the tasks run in article order.
        builder_calls.append(1)
        if len(builder_calls) == 2:
            raise RuntimeError("wiring failure")

        async def _on_scraped(event):
            processed.append(event.url)
        await bus.subscribe(ArticleScrapedEvent, _on_scraped)

    bus, published = await _recording_bus()
    pipeline = _pipeline(articles, test_async_sessionmaker, bus, article_downstream_builder=builder,
                         text_stage_concurrency=1)

    assert await pipeline.run() == 3

    assert processed == [articles[0].url, articles[2].url]
    assert [type(e) for e in published] == [TextPipelineCompletedEvent, PipelineCompletedEvent]


@pytest.mark.asyncio
async def test_failing_translation_task_is_settled_before_barrier_one(test_async_sessionmaker):
    from src.modules.intelligence.application.events import AnalysisCompletedEvent

    articles = _articles(2, "translate")
    attempts = []

    async def builder(session, bus, dispatch_rag):
        async def _on_scraped(event):
            await bus.publish(AnalysisCompletedEvent(analysis_id=uuid.uuid4(), article_id=uuid.uuid4()))
        await bus.subscribe(ArticleScrapedEvent, _on_scraped)

    class _FailingTranslation:
        async def handle(self, event):
            attempts.append(event)
            raise RuntimeError("translation provider down")

    async def translation_builder(session):
        return _FailingTranslation()

    bus, published = await _recording_bus()
    pipeline = _pipeline(articles, test_async_sessionmaker, bus, article_downstream_builder=builder,
                         translation_downstream_builder=translation_builder)

    assert await pipeline.run() == 2

    assert len(attempts) == 2
    assert [type(e) for e in published] == [TextPipelineCompletedEvent, PipelineCompletedEvent]


@pytest.mark.asyncio
async def test_rate_limited_llm_providers_are_reported(test_async_sessionmaker):
    articles = _articles(1, "llm")
    llm_service = MagicMock()
    llm_service.exhausted_providers = ["gemini", "claude"]
    bus, published = await _recording_bus()
    pipeline = _pipeline(articles, test_async_sessionmaker, bus, llm_service=llm_service)

    await pipeline.run()

    text_done, completed = published
    assert text_done.rate_limited_llm_providers == ("gemini", "claude")
    assert completed.rate_limited_llm_providers == ("gemini", "claude")

