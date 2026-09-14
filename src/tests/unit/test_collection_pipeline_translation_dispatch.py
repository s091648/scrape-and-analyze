"""fix/sanitize (translation fan-out): CollectionPipeline dispatches per-article
translation as its own detached SettlingTaskGroup task off AnalysisCompletedEvent
(Barrier 1.5), mirroring the RAG _dispatch_rag/_rag_tasks pattern — see
test_collection_pipeline_rag_dispatch_concurrency.py / rag_resilience.py, this
file's siblings for the translation side of the same shape."""
import asyncio
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.collection.collection_pipeline import CollectionPipeline
from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus
from src.modules.collection.application.use_cases import PipelineStats
from src.modules.collection.domain.value_objects import ScrapedArticle
from src.modules.intelligence.application.events import AnalysisCompletedEvent


@asynccontextmanager
async def _fake_session():
    yield MagicMock()


def _make_pipeline(*, translation_downstream_builder, article_downstream_builder=None,
                    async_sessionmaker_factory=None, translation_dispatch_concurrency=4):
    return CollectionPipeline(
        setting_repo=MagicMock(),
        scraper_factory=MagicMock(),
        event_bus=AsyncMock(),
        pipeline_stats=PipelineStats(),
        async_sessionmaker_factory=async_sessionmaker_factory or _fake_session,
        article_downstream_builder=article_downstream_builder or AsyncMock(),
        rag_downstream_builder=None,
        event_bus_factory=AsyncInMemoryEventBus,
        translation_downstream_builder=translation_downstream_builder,
        translation_dispatch_concurrency=translation_dispatch_concurrency,
    )


def _event():
    return AnalysisCompletedEvent(analysis_id=uuid.uuid4(), article_id=uuid.uuid4())


# ── _dispatch_translation: disabled vs enabled ───────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_translation_returns_none_when_disabled():
    """translation_downstream_builder=None must short-circuit — no task
    created, mirroring rag_downstream_builder's None-disables convention."""
    pipeline = _make_pipeline(translation_downstream_builder=None)

    result = await pipeline._dispatch_translation(_event())

    assert result is None
    assert await pipeline._translation_group.settle() == []


@pytest.mark.asyncio
async def test_dispatch_translation_fires_a_detached_task_when_enabled():
    """When enabled, _dispatch_translation must return immediately (task
    creation only) and track the task in _translation_group for Barrier 1.5,
    without itself awaiting _run_translation to completion."""
    handled = []

    async def _builder(session):
        handler = MagicMock()

        async def _handle(event):
            handled.append(event)
        handler.handle = _handle
        return handler

    pipeline = _make_pipeline(translation_downstream_builder=_builder)
    event = _event()

    task = await pipeline._dispatch_translation(event)

    assert task is not None
    assert task in pipeline._translation_group._tasks
    outcomes = await pipeline._translation_group.settle()
    assert outcomes == [None]
    assert handled == [event]


# ── _run_translation: session lifecycle + semaphore + builder wiring ────────

@pytest.mark.asyncio
async def test_run_translation_builds_handler_with_its_own_session_and_calls_handle():
    sessions_opened = 0
    seen_session = None

    @asynccontextmanager
    async def _tracked_session():
        nonlocal sessions_opened, seen_session
        sessions_opened += 1
        session = MagicMock()
        seen_session = session
        yield session

    built_with = []

    async def _builder(session):
        built_with.append(session)
        handler = MagicMock()
        handler.handle = AsyncMock()
        return handler

    pipeline = _make_pipeline(
        translation_downstream_builder=_builder,
        async_sessionmaker_factory=_tracked_session,
    )
    event = _event()

    await pipeline._run_translation(event)

    assert sessions_opened == 1
    assert built_with == [seen_session]


@pytest.mark.asyncio
async def test_run_translation_bounded_by_translation_dispatch_concurrency():
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

    async def _builder(session):
        handler = MagicMock()
        handler.handle = AsyncMock()
        return handler

    pipeline = _make_pipeline(
        translation_downstream_builder=_builder,
        async_sessionmaker_factory=_tracked_session,
        translation_dispatch_concurrency=2,
    )

    await asyncio.gather(*(pipeline._run_translation(_event()) for _ in range(6)))

    assert max_observed <= 2


# ── run(): subscribe wiring + Barrier 1.5 resilience ─────────────────────────

def _run_with_one_article(article_downstream_builder):
    """Builds a minimal CollectionPipeline that discovers/fetches exactly one
    article, so run() drives it through _process_article_text and the given
    article_downstream_builder gets to interact with that article's own bus."""
    setting = MagicMock(id="id-1", source_type="rss", url="https://example.com/feed")
    setting_repo = MagicMock()
    setting_repo.get_active_due.return_value = [setting]

    article = ScrapedArticle(title="A", url="https://example.com/a", source="rss",
                              content="c", published_at=None)
    executor = MagicMock()
    executor.exhausted_hosts = []
    executor.run_discover.return_value = [MagicMock()]

    def _fetch_all(fetch_tasks, on_result):
        on_result(article)
    executor.run_fetch_only.side_effect = _fetch_all

    return setting_repo, executor


@pytest.mark.asyncio
async def test_run_subscribes_translation_dispatch_when_builder_is_set():
    """The per-article bus must have _dispatch_translation subscribed to
    AnalysisCompletedEvent whenever translation_downstream_builder is set, so
    publishing that event on the per-article bus (as ArticleProcessedHandler
    normally does) actually reaches translation."""
    handled = []

    async def _translation_builder(session):
        handler = MagicMock()

        async def _handle(event):
            handled.append(event)
        handler.handle = _handle
        return handler

    async def _article_builder(session, bus, dispatch_rag):
        await bus.publish(AnalysisCompletedEvent(analysis_id=uuid.uuid4(), article_id=uuid.uuid4()))

    setting_repo, executor = _run_with_one_article(_article_builder)

    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=MagicMock(),
        event_bus=AsyncMock(),
        pipeline_stats=PipelineStats(),
        async_sessionmaker_factory=_fake_session,
        article_downstream_builder=_article_builder,
        rag_downstream_builder=None,
        event_bus_factory=AsyncInMemoryEventBus,
        executor=executor,
        article_repo=None,
        translation_downstream_builder=_translation_builder,
    )

    await pipeline.run()

    assert len(handled) == 1


@pytest.mark.asyncio
async def test_run_never_subscribes_translation_dispatch_when_builder_is_none():
    """Symmetric guard: without a translation_downstream_builder, publishing
    AnalysisCompletedEvent on the per-article bus must not error (no
    subscriber at all for it in that case, from this pipeline's side)."""
    async def _article_builder(session, bus, dispatch_rag):
        await bus.publish(AnalysisCompletedEvent(analysis_id=uuid.uuid4(), article_id=uuid.uuid4()))

    setting_repo, executor = _run_with_one_article(_article_builder)

    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=MagicMock(),
        event_bus=AsyncMock(),
        pipeline_stats=PipelineStats(),
        async_sessionmaker_factory=_fake_session,
        article_downstream_builder=_article_builder,
        rag_downstream_builder=None,
        event_bus_factory=AsyncInMemoryEventBus,
        executor=executor,
        article_repo=None,
        translation_downstream_builder=None,
    )

    await pipeline.run()  # must not raise


@pytest.mark.asyncio
async def test_barrier_1_5_logs_translation_task_failures_without_aborting_the_run():
    """A translation task that raises must be logged (translation_task_failed)
    at Barrier 1.5 and must not cancel or block the rest of the run — settle
    semantics, same as Barrier 2's rag_task_failed logging."""
    async def _translation_builder(session):
        handler = MagicMock()

        async def _handle(event):
            raise RuntimeError("translation blew up")
        handler.handle = _handle
        return handler

    async def _article_builder(session, bus, dispatch_rag):
        await bus.publish(AnalysisCompletedEvent(analysis_id=uuid.uuid4(), article_id=uuid.uuid4()))

    setting_repo, executor = _run_with_one_article(_article_builder)

    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=MagicMock(),
        event_bus=AsyncMock(),
        pipeline_stats=PipelineStats(),
        async_sessionmaker_factory=_fake_session,
        article_downstream_builder=_article_builder,
        rag_downstream_builder=None,
        event_bus_factory=AsyncInMemoryEventBus,
        executor=executor,
        article_repo=None,
        translation_downstream_builder=_translation_builder,
    )

    with patch("src.infrastructure.collection.collection_pipeline.logger") as mock_logger:
        result = await pipeline.run()  # must not raise despite the translation failure

    assert result == 1
    error_calls = [c for c in mock_logger.error.call_args_list if c.args and c.args[0] == "translation_task_failed"]
    assert len(error_calls) == 1
    assert error_calls[0].kwargs["error_type"] == "RuntimeError"
