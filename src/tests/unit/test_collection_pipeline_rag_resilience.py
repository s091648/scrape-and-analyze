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
from src.modules.collection.application.use_cases import PipelineStats


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
    """The embedding RPD cap, once hit, raises RateLimitExhausted on every
    subsequent call — so after the first, no further RAG ingestion should even
    open a session; the untried article is just queued for the backfill cron."""
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
