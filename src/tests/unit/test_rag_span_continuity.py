"""024-async-pipeline-refactor research.md item 8: "Verification needed at
implementation time" — confirm empirically that OTel span parent/child
continuity survives the `asyncio.create_task()` boundary between an
article's own `article.pipeline` span (CollectionPipeline._process_article_text)
and its detached RAG child task's `article.rag_ingest` span
(AsyncRagIngestionHandler.handle, created inside the task `_dispatch_rag`
spawns via `asyncio.create_task`, per research.md item 5).

Uses a real OTel SDK TracerProvider (no exporter needed — SpanContext/parent
linkage is populated regardless of where spans are sent) patched into both
call sites, rather than the process-global `trace.set_tracer_provider()`
(which can only be set once per process and would risk cross-test pollution)."""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opentelemetry.sdk.trace import TracerProvider

from src.infrastructure.collection.collection_pipeline import CollectionPipeline
from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus
from src.modules.collection.application.use_cases import PipelineStats
from src.modules.collection.domain.value_objects import ScrapedArticle
from src.modules.collection.application.events import ArticleScrapedEvent
from src.shared.application.events import ArticleProcessedEvent
from src.modules.intelligence.application.event_handlers.rag_ingestion_handler import AsyncRagIngestionHandler


@asynccontextmanager
async def _fake_session():
    yield MagicMock()


@pytest.mark.asyncio
async def test_rag_task_span_nests_under_the_article_pipeline_span():
    provider = TracerProvider()
    tracer = provider.get_tracer("test")

    article = ScrapedArticle(title="A1", url="https://example.com/1", source="test",
                              content="c1", published_at=None)

    class _StubUseCase:
        async def execute(self, article, full_text):
            return None

    rag_handler = AsyncRagIngestionHandler(use_case=_StubUseCase(), event_bus=AsyncMock())

    captured_rag_span_context = {}

    async def _use_case_execute_capturing(article_arg, full_text):
        from opentelemetry import trace as _ot
        span = _ot.get_current_span()
        ctx = span.get_span_context()
        captured_rag_span_context["trace_id"] = ctx.trace_id
        captured_rag_span_context["span_id"] = ctx.span_id
        return None

    rag_handler._use_case = MagicMock()
    rag_handler._use_case.execute = AsyncMock(side_effect=_use_case_execute_capturing)

    async def _rag_downstream_builder(rag_session):
        return rag_handler

    captured_article_span_context = {}

    async def _tracking_builder(session, bus, dispatch_rag):
        async def _on_scraped(event):
            from opentelemetry import trace as _ot
            span = _ot.get_current_span()
            ctx = span.get_span_context()
            captured_article_span_context["trace_id"] = ctx.trace_id
            captured_article_span_context["span_id"] = ctx.span_id
            fake_article = MagicMock(id="a1", url=article.url, title=article.title, content="")
            await dispatch_rag(ArticleProcessedEvent(article=fake_article))
        await bus.subscribe(ArticleScrapedEvent, _on_scraped)

    setting = MagicMock(id="id-1", source_type="rss", url="https://example.com/feed")
    mock_setting_repo = MagicMock()
    mock_setting_repo.get_active_due.return_value = [setting]

    mock_executor = MagicMock()
    mock_executor.exhausted_hosts = []
    mock_executor.run_discover.return_value = [MagicMock()]

    def fetch_one(fetch_tasks, on_result):
        on_result(article)
    mock_executor.run_fetch_only.side_effect = fetch_one

    with patch("src.infrastructure.collection.collection_pipeline.get_tracer", return_value=tracer), \
         patch("src.modules.intelligence.application.event_handlers.rag_ingestion_handler._tracer", tracer):
        pipeline = CollectionPipeline(
            setting_repo=mock_setting_repo,
            scraper_factory=MagicMock(),
            event_bus=AsyncMock(),
            pipeline_stats=PipelineStats(),
            async_sessionmaker_factory=lambda: _fake_session(),
            article_downstream_builder=_tracking_builder,
            rag_downstream_builder=_rag_downstream_builder,
            event_bus_factory=AsyncInMemoryEventBus,
            executor=mock_executor,
            article_repo=None,
        )
        await pipeline.run()

    assert captured_article_span_context, "article.pipeline span was never current"
    assert captured_rag_span_context, "article.rag_ingest span was never current"

    # Same trace — the detached RAG task's span is part of the same trace as
    # the article's own pipeline span, not a disconnected root span.
    assert captured_rag_span_context["trace_id"] == captured_article_span_context["trace_id"]
    # Genuinely nested — the RAG span is NOT the same span as article.pipeline
    # (it's a real child, not just inheriting the same span by accident).
    assert captured_rag_span_context["span_id"] != captured_article_span_context["span_id"]
