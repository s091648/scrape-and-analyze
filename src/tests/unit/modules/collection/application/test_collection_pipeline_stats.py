from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.collection.application.use_cases import PipelineStats
from src.modules.collection.application.events import PipelineCompletedEvent
from src.modules.collection.domain.value_objects import ScrapedArticle


def _make_setting(source="arxiv", source_type="arxiv"):
    s = MagicMock()
    s.source = source
    s.source_type = source_type
    s.url = "https://export.arxiv.org/api/query"
    s.id = "test-id"
    return s


@pytest.mark.asyncio
async def test_pipeline_publishes_pipeline_completed_event():
    """024-async-pipeline-refactor: the run-level event_bus only ever sees the
    two barrier events now (TextPipelineCompletedEvent, PipelineCompletedEvent)
    — per-article events go through a fresh bus built by
    article_downstream_builder inside each article's own asyncio.Task, so this
    test's article_downstream_builder is a no-op; it isn't what's under test
    here (that's covered by test_composition_root.py's per-article-bus tests)."""
    from src.infrastructure.collection.collection_pipeline import CollectionPipeline
    from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus

    pipeline_stats = PipelineStats()
    event_bus = AsyncMock()

    article = MagicMock(spec=ScrapedArticle)
    article.url = "http://x.com/1"
    article.source = "arxiv"
    article.title = "T"
    article.content = "C"
    article.published_at = None
    article.topic_id = None
    article.authors = []
    article.extra = {}

    setting_repo = MagicMock()
    setting_repo.get_active_due.return_value = [_make_setting("arxiv")]

    scraper_factory = MagicMock()

    executor = MagicMock()
    mock_fetch_task = MagicMock()
    executor.run_discover.return_value = [mock_fetch_task]

    def _run_fetch_only(fetch_tasks, on_result):
        on_result(article)
    executor.run_fetch_only.side_effect = _run_fetch_only

    @asynccontextmanager
    async def _fake_session():
        yield MagicMock()

    async def article_downstream_builder(session, bus, dispatch_rag):
        pass  # no-op — not what's under test here

    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=scraper_factory,
        event_bus=event_bus,
        pipeline_stats=pipeline_stats,
        async_sessionmaker_factory=lambda: _fake_session(),
        article_downstream_builder=article_downstream_builder,
        rag_downstream_builder=None,
        event_bus_factory=AsyncInMemoryEventBus,
        executor=executor,
    )
    await pipeline.run()

    published_events = [
        call.args[0] for call in event_bus.publish.call_args_list
        if isinstance(call.args[0], PipelineCompletedEvent)
    ]
    assert len(published_events) == 1
    assert published_events[0].execution.duration_seconds >= 0
