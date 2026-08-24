"""US2 (024-async-pipeline-refactor) tests for CollectionPipeline's two-barrier
split: Barrier 1 (TextPipelineCompletedEvent — search index + cache) must
settle without waiting on RAG; Barrier 2 (PipelineCompletedEvent) still waits
for everything including RAG.

No real Postgres/Redis connection needed — these exercise CollectionPipeline's
own orchestration with fake session/downstream builders and Barrier-1
subscriber stand-ins (representing SearchIndexRebuildHandler,
CacheInvalidationHandler, CacheWarmupHandler), matching the pattern in
test_collection_pipeline_concurrency.py."""
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


def _make_pipeline(article_downstream_builder, *, rag_downstream_builder, event_bus, n_articles):
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

    return CollectionPipeline(
        setting_repo=mock_setting_repo,
        scraper_factory=MagicMock(),
        event_bus=event_bus,
        pipeline_stats=PipelineStats(),
        async_sessionmaker_factory=lambda: _fake_session(),
        article_downstream_builder=article_downstream_builder,
        rag_downstream_builder=rag_downstream_builder,
        event_bus_factory=AsyncInMemoryEventBus,
        executor=mock_executor,
        article_repo=None,
    )


# ---------------------------------------------------------------------------
# T044: Barrier 1 (search index + cache) settles before slow RAG resolves
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_barrier_one_handlers_complete_before_slow_rag_task_resolves():
    RAG_DELAY = 0.3
    barrier_one_call_order = []
    rag_done_at = []

    async def _search_index_rebuild_stub(event):
        barrier_one_call_order.append(("search_index_rebuild", time.monotonic()))

    async def _cache_invalidation_stub(event):
        barrier_one_call_order.append(("cache_invalidation", time.monotonic()))

    async def _cache_warmup_stub(event):
        barrier_one_call_order.append(("cache_warmup", time.monotonic()))

    async def _tracking_builder(session, bus, dispatch_rag):
        async def _on_scraped(event):
            await dispatch_rag(event)
        await bus.subscribe(ArticleScrapedEvent, _on_scraped)

    class _SlowRagHandler:
        async def handle(self, event):
            await asyncio.sleep(RAG_DELAY)
            rag_done_at.append(time.monotonic())

    async def _rag_downstream_builder(rag_session):
        return _SlowRagHandler()

    from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus
    event_bus = AsyncInMemoryEventBus()
    # Subscribe order matches bootstrap.py's real wiring: search index, then
    # cache invalidation, then cache warmup — all on TextPipelineCompletedEvent.
    await event_bus.subscribe(TextPipelineCompletedEvent, _search_index_rebuild_stub)
    await event_bus.subscribe(TextPipelineCompletedEvent, _cache_invalidation_stub)
    await event_bus.subscribe(TextPipelineCompletedEvent, _cache_warmup_stub)

    pipeline = _make_pipeline(
        _tracking_builder,
        rag_downstream_builder=_rag_downstream_builder,
        event_bus=event_bus,
        n_articles=2,
    )

    await pipeline.run()

    assert len(barrier_one_call_order) == 3
    assert [name for name, _ in barrier_one_call_order] == [
        "search_index_rebuild", "cache_invalidation", "cache_warmup",
    ]
    assert len(rag_done_at) == 2

    barrier_one_finished_at = max(t for _, t in barrier_one_call_order)
    assert barrier_one_finished_at < min(rag_done_at)


# ---------------------------------------------------------------------------
# T046: zero RAG-eligible articles still fires TextPipelineCompletedEvent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_text_pipeline_completed_event_fires_with_no_rag_eligible_articles():
    barrier_one_calls = []

    async def _search_index_rebuild_stub(event):
        barrier_one_calls.append(event)

    async def _no_rag_builder(session, bus, dispatch_rag):
        # No handler subscribes to ArticleProcessedEvent / calls dispatch_rag —
        # simulates articles with no RAG-eligible content.
        pass

    from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus
    event_bus = AsyncInMemoryEventBus()
    await event_bus.subscribe(TextPipelineCompletedEvent, _search_index_rebuild_stub)

    pipeline = _make_pipeline(
        _no_rag_builder,
        rag_downstream_builder=None,
        event_bus=event_bus,
        n_articles=3,
    )

    result = await pipeline.run()

    assert result == 3
    assert len(barrier_one_calls) == 1
    assert isinstance(barrier_one_calls[0], TextPipelineCompletedEvent)
