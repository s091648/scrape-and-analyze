from opentelemetry import trace as _otel_trace

from shared.observability.traceback_filter import format_filtered_exc
from src.modules.intelligence.application.use_cases.ingest_article_for_rag import IngestArticleForRagUseCase
from src.modules.intelligence.application.events.rag_ingestion_failed import RagIngestionFailedEvent
from src.shared.logging import get_logger
from src.infrastructure.shared.logging import get_correlation_id

logger = get_logger(__name__)
_tracer = _otel_trace.get_tracer(__name__)


class RagIngestionHandler:
    def __init__(self, use_case: IngestArticleForRagUseCase, event_bus) -> None:
        self._use_case = use_case
        self._event_bus = event_bus

    def handle(self, event) -> None:
        import time as _time
        article_id = event.article.id
        article_url = event.article.url
        article_title = getattr(event.article, 'title', '') or ''
        content_chars = len(event.article.content) if event.article.content else 0
        with _tracer.start_as_current_span("article.rag_ingest") as span:
            span.set_attribute("article.id", str(article_id))
            span.set_attribute("article.url", str(article_url))
            span.set_attribute("article.title", article_title)
            span.set_attribute("article.content_chars", content_chars)
            _start = _time.monotonic()
            full_text = getattr(event, 'full_text', '') or ''
            span.set_attribute("rag_ingest.full_text_chars", len(full_text))
            try:
                self._use_case.execute(event.article, full_text)
                duration = round(_time.monotonic() - _start, 3)
                span.set_attribute("rag_ingest.success", True)
                span.set_attribute("rag_ingest.duration_seconds", duration)
            except Exception as exc:
                duration = round(_time.monotonic() - _start, 3)
                span.set_attribute("rag_ingest.success", False)
                span.set_attribute("rag_ingest.error_type", type(exc).__name__)
                span.set_attribute("rag_ingest.duration_seconds", duration)
                logger.exception(
                    "rag_ingest_failed",
                    article_id=str(article_id),
                    article_url=str(article_url),
                    article_title=article_title,
                    content_chars=content_chars,
                    duration_seconds=duration,
                    error_type=type(exc).__name__,
                )
                self._event_bus.publish(RagIngestionFailedEvent(
                    article_id=article_id,
                    article_url=article_url,
                    exception_type=type(exc).__name__,
                    exception_message=str(exc),
                    context={"span": "article.rag_ingest", "content_chars": content_chars},
                    traceback=format_filtered_exc(exc),
                    correlation_id=get_correlation_id() or None,
                ))


class AsyncRagIngestionHandler:
    """024-async-pipeline-refactor: async sibling of RagIngestionHandler — new,
    separate class (paired with AsyncIngestArticleForRagUseCase, which
    RagIngestionHandler's use case type wouldn't accept). `handle()` is
    `async def`, awaiting both the use case and the async EventBus.publish().
    Constructed only inside build_collection_pipeline() and dispatched as a
    detached asyncio.Task (research.md item 5) rather than awaited inline, so
    one article's RAG ingestion never blocks another's — or its own text-stage
    completion."""

    def __init__(self, use_case, event_bus) -> None:
        self._use_case = use_case
        self._event_bus = event_bus

    async def handle(self, event) -> None:
        import time as _time
        article_id = event.article.id
        article_url = event.article.url
        article_title = getattr(event.article, 'title', '') or ''
        content_chars = len(event.article.content) if event.article.content else 0
        with _tracer.start_as_current_span("article.rag_ingest") as span:
            span.set_attribute("article.id", str(article_id))
            span.set_attribute("article.url", str(article_url))
            span.set_attribute("article.title", article_title)
            span.set_attribute("article.content_chars", content_chars)
            _start = _time.monotonic()
            full_text = getattr(event, 'full_text', '') or ''
            span.set_attribute("rag_ingest.full_text_chars", len(full_text))
            try:
                await self._use_case.execute(event.article, full_text)
                duration = round(_time.monotonic() - _start, 3)
                span.set_attribute("rag_ingest.success", True)
                span.set_attribute("rag_ingest.duration_seconds", duration)
            except Exception as exc:
                duration = round(_time.monotonic() - _start, 3)
                span.set_attribute("rag_ingest.success", False)
                span.set_attribute("rag_ingest.error_type", type(exc).__name__)
                span.set_attribute("rag_ingest.duration_seconds", duration)
                logger.exception(
                    "rag_ingest_failed",
                    article_id=str(article_id),
                    article_url=str(article_url),
                    article_title=article_title,
                    content_chars=content_chars,
                    duration_seconds=duration,
                    error_type=type(exc).__name__,
                )
                await self._event_bus.publish(RagIngestionFailedEvent(
                    article_id=article_id,
                    article_url=article_url,
                    exception_type=type(exc).__name__,
                    exception_message=str(exc),
                    context={"span": "article.rag_ingest", "content_chars": content_chars},
                    traceback=format_filtered_exc(exc),
                    correlation_id=get_correlation_id() or None,
                ))
