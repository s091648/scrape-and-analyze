"""US1 (024-async-pipeline-refactor) concurrency tests for CollectionPipeline.run().

These exercise CollectionPipeline's own orchestration logic (per-article
asyncio.Task fan-out, RAG detachment) using fake session/downstream builders —
no real Postgres connection needed, so these do not use @pytest.mark.integration
or the db_session/async_db_session fixtures, matching the "no autouse DB
fixture" convention in src/tests/integration/conftest.py.

T037: a batch of N articles' downstream processing overlaps in wall-clock time.
T038: one article's artificially-slowed RAG ingestion does not delay Barrier 1
      (TextPipelineCompletedEvent) or any other article's text-stage completion.
"""
import time
import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.collection.collection_pipeline import CollectionPipeline
from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus
from src.modules.collection.application.use_cases import PipelineStats
from src.modules.collection.domain.value_objects import ScrapedArticle
from src.modules.collection.application.events import ArticleScrapedEvent, TextPipelineCompletedEvent


@asynccontextmanager
async def _fake_session():
    yield MagicMock()


def _make_pipeline(article_downstream_builder, *, rag_downstream_builder=None,
                    event_bus=None, n_articles=5):
    articles = [
        ScrapedArticle(title=f"A{i}", url=f"https://example.com/{i}", source="test",
                        content=f"c{i}", published_at=None)
        for i in range(n_articles)
    ]

    setting = MagicMock(id="id-1", source_type="rss", url="https://example.com/feed")
    mock_setting_repo = MagicMock()
    mock_setting_repo.get_active_due.return_value = [setting]

    mock_executor = MagicMock()
    mock_executor.exhausted_hosts = []
    mock_executor.run_discover.return_value = [MagicMock() for _ in articles]

    def fetch_all(fetch_tasks, on_result):
        for a in articles:
            on_result(a)
    mock_executor.run_fetch_only.side_effect = fetch_all

    pipeline = CollectionPipeline(
        setting_repo=mock_setting_repo,
        scraper_factory=MagicMock(),
        event_bus=event_bus or AsyncMock(),
        pipeline_stats=PipelineStats(),
        async_sessionmaker_factory=lambda: _fake_session(),
        article_downstream_builder=article_downstream_builder,
        rag_downstream_builder=rag_downstream_builder,
        event_bus_factory=AsyncInMemoryEventBus,
        executor=mock_executor,
        article_repo=None,
    )
    return pipeline


# ---------------------------------------------------------------------------
# T037: per-article downstream processing overlaps in wall-clock time
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_article_downstream_processing_overlaps_in_wall_clock_time():
    N = 5
    DELAY = 0.2
    intervals = []

    async def _slow_builder(session, bus, dispatch_rag):
        start = time.monotonic()
        await asyncio.sleep(DELAY)
        intervals.append((start, time.monotonic()))

    pipeline = _make_pipeline(_slow_builder, n_articles=N)

    t0 = time.monotonic()
    await pipeline.run()
    elapsed = time.monotonic() - t0

    assert len(intervals) == N
    # Sequential execution would take N * DELAY (~1.0s); real overlap keeps
    # total wall-clock close to a single DELAY (~0.2s) regardless of N.
    assert elapsed < N * DELAY * 0.6

    # Direct overlap proof: at least one article's interval starts before
    # another article's interval has ended.
    intervals.sort(key=lambda iv: iv[0])
    overlapping = any(
        intervals[i][0] < intervals[i - 1][1] for i in range(1, len(intervals))
    )
    assert overlapping


# ---------------------------------------------------------------------------
# T038: a slow RAG ingestion does not delay Barrier 1 or other articles
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_slow_rag_ingestion_does_not_delay_barrier_one_or_other_articles():
    RAG_DELAY = 0.3
    text_done_times = []
    rag_done_times = []
    publish_events = []

    async def _tracking_builder(session, bus, dispatch_rag):
        async def _on_scraped(event):
            text_done_times.append((event.url, time.monotonic()))
            await dispatch_rag(event)
        await bus.subscribe(ArticleScrapedEvent, _on_scraped)

    class _SlowRagHandler:
        async def handle(self, event):
            await asyncio.sleep(RAG_DELAY)
            rag_done_times.append((event.url, time.monotonic()))

    async def _rag_downstream_builder(rag_session):
        return _SlowRagHandler()

    mock_event_bus = AsyncMock()

    async def _record_publish(event):
        publish_events.append((type(event).__name__, time.monotonic()))
    mock_event_bus.publish.side_effect = _record_publish

    pipeline = _make_pipeline(
        _tracking_builder,
        rag_downstream_builder=_rag_downstream_builder,
        event_bus=mock_event_bus,
        n_articles=2,
    )

    t0 = time.monotonic()
    await pipeline.run()

    assert len(text_done_times) == 2
    assert len(rag_done_times) == 2

    text_barrier_time = next(t for name, t in publish_events if name == "TextPipelineCompletedEvent") - t0
    rag_completion_times = [t - t0 for _, t in rag_done_times]

    # Barrier 1 fires as soon as both articles' (fast) text stages settle —
    # well before either article's slow RAG task resolves.
    assert text_barrier_time < min(rag_completion_times)
    # Both articles' text stages complete close together, not staggered by
    # the other article's RAG latency (RAG is detached, never awaited inline).
    text_times = [t - t0 for _, t in text_done_times]
    assert max(text_times) - min(text_times) < RAG_DELAY
