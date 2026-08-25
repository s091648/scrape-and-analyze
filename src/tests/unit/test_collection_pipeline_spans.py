"""
Unit tests for OTel stage spans added to CollectionPipeline.run().

Verifies that start_as_current_span is called with the expected span names
when the pipeline runs. Uses a minimal mock setup to avoid DB / scraper deps.

024-async-pipeline-refactor: CollectionPipeline.run() is now async, and its
constructor takes three new required collaborators (async_sessionmaker_factory,
article_downstream_builder, rag_downstream_builder) for the per-article
concurrent downstream — mocked here since these tests only exercise the
upstream discover/fetch/publish spans, not per-article processing itself.
"""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


def _make_pipeline(has_due_settings: bool = True):
    """Build a CollectionPipeline with all deps mocked."""
    from src.infrastructure.collection.collection_pipeline import CollectionPipeline
    from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus

    setting_repo = MagicMock()
    if has_due_settings:
        mock_setting = MagicMock()
        mock_setting.source_type = "rss"
        mock_setting.url = "https://example.com/feed.xml"
        mock_setting.id = "setting-1"
        setting_repo.get_active_due.return_value = [mock_setting]
    else:
        setting_repo.get_active_due.return_value = []

    scraper_factory = MagicMock()
    event_bus = AsyncMock()
    pipeline_stats = MagicMock()
    pipeline_stats.get_results.return_value = []
    executor = MagicMock()
    executor.run_discover = MagicMock(return_value=[])
    executor.run_fetch_only = MagicMock()

    async def async_sessionmaker_factory():
        raise AssertionError("not expected to be called — no articles published in these tests")

    async def article_downstream_builder(session, bus, dispatch_rag):
        raise AssertionError("not expected to be called — no articles published in these tests")

    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=scraper_factory,
        event_bus=event_bus,
        pipeline_stats=pipeline_stats,
        async_sessionmaker_factory=async_sessionmaker_factory,
        article_downstream_builder=article_downstream_builder,
        rag_downstream_builder=None,
        event_bus_factory=AsyncInMemoryEventBus,
        executor=executor,
    )
    return pipeline, event_bus


class TestCollectionPipelineSpans:
    @pytest.mark.asyncio
    async def test_discover_span_created(self):
        pipeline, _ = _make_pipeline()
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value = mock_span

        with patch("src.infrastructure.shared.observability.otel_tracing._tracer", mock_tracer):
            await pipeline.run()

        span_names = [c.args[0] for c in mock_tracer.start_as_current_span.call_args_list]
        assert "pipeline.discover" in span_names

    @pytest.mark.asyncio
    async def test_fetch_span_created(self):
        pipeline, _ = _make_pipeline()
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value = mock_span

        with patch("src.infrastructure.shared.observability.otel_tracing._tracer", mock_tracer):
            await pipeline.run()

        span_names = [c.args[0] for c in mock_tracer.start_as_current_span.call_args_list]
        assert "pipeline.fetch" in span_names

    @pytest.mark.asyncio
    async def test_publish_articles_span_created(self):
        pipeline, _ = _make_pipeline()
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value = mock_span

        with patch("src.infrastructure.shared.observability.otel_tracing._tracer", mock_tracer):
            await pipeline.run()

        span_names = [c.args[0] for c in mock_tracer.start_as_current_span.call_args_list]
        assert "pipeline.publish_articles" in span_names

    @pytest.mark.asyncio
    async def test_no_span_error_when_tracer_is_noop(self):
        """Pipeline runs without errors when tracer is no-op (env vars not set)."""
        pipeline, _event_bus = _make_pipeline(has_due_settings=False)
        # No patch — uses actual (potentially no-op) tracer
        result = await pipeline.run()
        assert result == 0  # no articles published (empty due list)
