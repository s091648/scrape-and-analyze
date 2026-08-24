"""US1 (024-async-pipeline-refactor) T039: no two concurrently-running article
asyncio.Tasks ever hold the same AsyncSession instance.

CollectionPipeline._process_article_text() opens `async with
self._async_sessionmaker_factory() as session:` fresh per article — this test
asserts that behavior via object-identity, with an artificial delay to force
genuine overlap between article tasks while their sessions are open."""
import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.collection.collection_pipeline import CollectionPipeline
from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus
from src.modules.collection.application.use_cases import PipelineStats
from src.modules.collection.domain.value_objects import ScrapedArticle


@pytest.mark.asyncio
async def test_no_two_concurrent_article_tasks_share_an_async_session():
    N = 5
    seen_session_ids = []

    def _session_factory():
        @asynccontextmanager
        async def _ctx():
            # A fresh, unique object every call — mirrors get_async_sessionmaker()
            # producing a distinct AsyncSession per invocation.
            yield object()
        return _ctx()

    async def _tracking_builder(session, bus, dispatch_rag):
        seen_session_ids.append(id(session))
        # Force overlap: without this, tasks could complete one after another
        # inside asyncio.gather's scheduling and the test would prove nothing.
        await asyncio.sleep(0.05)

    articles = [
        ScrapedArticle(title=f"A{i}", url=f"https://example.com/{i}", source="test",
                        content=f"c{i}", published_at=None)
        for i in range(N)
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
        event_bus=AsyncMock(),
        pipeline_stats=PipelineStats(),
        async_sessionmaker_factory=_session_factory,
        article_downstream_builder=_tracking_builder,
        rag_downstream_builder=None,
        event_bus_factory=AsyncInMemoryEventBus,
        executor=mock_executor,
        article_repo=None,
    )

    await pipeline.run()

    assert len(seen_session_ids) == N
    assert len(set(seen_session_ids)) == N, "two or more article tasks shared the same AsyncSession object"
