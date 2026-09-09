"""fix/scraper_failure follow-up: the per-article text stage (Barrier 1) fans
out one asyncio.Task per article at once. Without a bound, a large run opens one
cold pooled connection per article simultaneously — the asyncpg connect
starvation this change addresses. `text_stage_concurrency` (a BoundedSemaphore
gating _process_article_text's body, before the span/session are opened) caps
that burst; a blocked task just waits, nothing is dropped.

Sibling of test_collection_pipeline_rag_dispatch_concurrency.py (same shape for
the RAG side's _rag_dispatch_semaphore)."""
import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.collection.collection_pipeline import CollectionPipeline
from src.modules.collection.application.use_cases import PipelineStats
from src.modules.collection.domain.value_objects import ScrapedArticle


def _make_pipeline(text_stage_concurrency, article_downstream_builder):
    @asynccontextmanager
    async def _fake_session():
        yield MagicMock()

    def _bus_factory():
        bus = MagicMock()
        bus.publish = AsyncMock()
        return bus

    return CollectionPipeline(
        setting_repo=MagicMock(),
        scraper_factory=MagicMock(),
        event_bus=AsyncMock(),
        pipeline_stats=PipelineStats(),
        async_sessionmaker_factory=_fake_session,
        article_downstream_builder=article_downstream_builder,
        rag_downstream_builder=None,
        event_bus_factory=_bus_factory,
        text_stage_concurrency=text_stage_concurrency,
    )


def _articles(n):
    return [
        ScrapedArticle(title=f"A{i}", url=f"https://example.com/{i}", source="test",
                       content=f"c{i}", published_at=None)
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_text_stage_concurrency_bounds_concurrent_article_tasks():
    in_flight = 0
    max_observed = 0
    calls = 0

    async def _tracking_builder(session, bus, dispatch_rag):
        nonlocal in_flight, max_observed, calls
        calls += 1
        in_flight += 1
        max_observed = max(max_observed, in_flight)
        try:
            await asyncio.sleep(0.02)
        finally:
            in_flight -= 1

    pipeline = _make_pipeline(text_stage_concurrency=2, article_downstream_builder=_tracking_builder)

    await asyncio.gather(*(pipeline._process_article_text(a) for a in _articles(6)))

    assert max_observed <= 2
    assert calls == 6  # every article still ran — the semaphore serializes, never drops


@pytest.mark.asyncio
async def test_text_stage_semaphore_does_not_deadlock_when_fully_claimed():
    """A task that can't get a slot waits for one; once holders release, the
    queued tasks all proceed. Bounded by a wall-clock timeout so a regression
    that deadlocks fails loudly instead of hanging the suite."""
    release = asyncio.Event()
    started = 0

    async def _builder(session, bus, dispatch_rag):
        nonlocal started
        started += 1
        await release.wait()

    pipeline = _make_pipeline(text_stage_concurrency=1, article_downstream_builder=_builder)

    gathered = asyncio.gather(*(pipeline._process_article_text(a) for a in _articles(4)))
    await asyncio.sleep(0.05)
    assert started == 1  # only one holds the single slot; the other 3 are queued

    release.set()
    await asyncio.wait_for(gathered, timeout=5)
    assert started == 4


@pytest.mark.asyncio
async def test_default_text_stage_concurrency_matches_settings():
    from src.config.settings import TEXT_STAGE_CONCURRENCY

    pipeline = _make_pipeline(
        text_stage_concurrency=TEXT_STAGE_CONCURRENCY,
        article_downstream_builder=AsyncMock(),
    )
    assert pipeline._text_stage_semaphore._value == TEXT_STAGE_CONCURRENCY
