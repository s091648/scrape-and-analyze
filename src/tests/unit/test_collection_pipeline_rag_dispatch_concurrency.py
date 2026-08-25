"""024-async-pipeline-refactor US6 follow-up (research.md item 11): concurrent
RAG-ingesting articles in the live pipeline are bounded by
rag_dispatch_concurrency (a BoundedSemaphore gating _run_rag_ingestion's body)
— each concurrently in-flight article holds a real, unpooled Postgres
connection (NullPool, src/infrastructure/persistence/database.py), so this is
unbounded article volume vs. a bounded number of real DB connections, not an
embedding-throughput concern (that's RAG_DENSE_RPM/RAG_EMBED_BATCH_SIZE)."""
import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.collection.collection_pipeline import CollectionPipeline
from src.modules.collection.application.use_cases import PipelineStats


def _make_pipeline(rag_dispatch_concurrency, async_sessionmaker_factory, rag_downstream_builder):
    return CollectionPipeline(
        setting_repo=MagicMock(),
        scraper_factory=MagicMock(),
        event_bus=AsyncMock(),
        pipeline_stats=PipelineStats(),
        async_sessionmaker_factory=async_sessionmaker_factory,
        article_downstream_builder=AsyncMock(),
        rag_downstream_builder=rag_downstream_builder,
        event_bus_factory=MagicMock(),
        rag_dispatch_concurrency=rag_dispatch_concurrency,
    )


@pytest.mark.asyncio
async def test_rag_dispatch_concurrency_bounds_concurrent_sessions():
    in_flight = 0
    max_observed = 0

    @asynccontextmanager
    async def _tracked_session():
        nonlocal in_flight, max_observed
        in_flight += 1
        max_observed = max(max_observed, in_flight)
        try:
            await asyncio.sleep(0.02)
            yield MagicMock()
        finally:
            in_flight -= 1

    async def _rag_downstream_builder(session):
        handler = MagicMock()
        handler.handle = AsyncMock()
        return handler

    pipeline = _make_pipeline(
        rag_dispatch_concurrency=2,
        async_sessionmaker_factory=_tracked_session,
        rag_downstream_builder=_rag_downstream_builder,
    )

    await asyncio.gather(*(pipeline._dispatch_rag(MagicMock()) for _ in range(6)))
    await asyncio.gather(*pipeline._rag_tasks)

    assert max_observed <= 2


@pytest.mark.asyncio
async def test_dispatch_rag_does_not_block_on_the_semaphore():
    """_dispatch_rag() itself must return immediately (task creation only) even
    when the semaphore is fully claimed — the block happens inside the
    detached task's body, never on the caller triggering ArticleProcessedEvent
    (FR-002: RAG must never delay that article's own text-stage completion)."""
    release = asyncio.Event()

    @asynccontextmanager
    async def _blocking_session():
        await release.wait()
        yield MagicMock()

    async def _rag_downstream_builder(session):
        handler = MagicMock()
        handler.handle = AsyncMock()
        return handler

    pipeline = _make_pipeline(
        rag_dispatch_concurrency=1,
        async_sessionmaker_factory=_blocking_session,
        rag_downstream_builder=_rag_downstream_builder,
    )

    await asyncio.wait_for(
        asyncio.gather(*(pipeline._dispatch_rag(MagicMock()) for _ in range(5))),
        timeout=5,
    )
    assert len(pipeline._rag_tasks) == 5

    release.set()
    await asyncio.gather(*pipeline._rag_tasks)


@pytest.mark.asyncio
async def test_default_rag_dispatch_concurrency_matches_settings():
    from src.config.settings import RAG_DISPATCH_CONCURRENCY

    @asynccontextmanager
    async def _fake_session():
        yield MagicMock()

    pipeline = _make_pipeline(
        rag_dispatch_concurrency=RAG_DISPATCH_CONCURRENCY,
        async_sessionmaker_factory=_fake_session,
        rag_downstream_builder=AsyncMock(),
    )
    assert pipeline._rag_dispatch_semaphore._value == RAG_DISPATCH_CONCURRENCY
