from opentelemetry import trace as _otel_trace
from opentelemetry.trace import StatusCode

try:  # optional dependency — RAG SDK isn't always installed (see build_rag_ingestion_service)
    from chatbot_plugin_sdk import RateLimitExhausted
except ModuleNotFoundError:  # pragma: no cover - exercised only where the SDK is absent
    class RateLimitExhausted(Exception):  # type: ignore[no-redef]
        """Fallback stand-in so `except RateLimitExhausted` is always valid."""

from shared.enums.observability import SpanName
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
        with _tracer.start_as_current_span(SpanName.ARTICLE_RAG_INGEST) as span:
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
                span.record_exception(exc)
                span.set_status(StatusCode.ERROR, type(exc).__name__)
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
                    context={"span": SpanName.ARTICLE_RAG_INGEST.value, "content_chars": content_chars},
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
    completion.

    `parent_span` is the article.pipeline span this ingestion belongs to,
    captured by CollectionPipeline._dispatch_rag while that span was current.
    It's passed explicitly (rather than relying on implicit contextvar
    propagation across asyncio.create_task) so article.rag_ingest is a proper
    child of article.pipeline even though it starts after the text stage
    returned. The pipeline span is kept open until this task settles — see
    CollectionPipeline._run_rag_ingestion — so its duration/subtree actually
    contain the RAG work.
    """

    def __init__(self, use_case, event_bus) -> None:
        self._use_case = use_case
        self._event_bus = event_bus

    async def handle(self, event, parent_span=None) -> None:
        import time as _time
        article_id = event.article.id
        article_url = event.article.url
        article_title = getattr(event.article, 'title', '') or ''
        content_chars = len(event.article.content) if event.article.content else 0

        ctx = (
            _otel_trace.set_span_in_context(parent_span)
            if parent_span is not None
            else None
        )
        with _tracer.start_as_current_span(SpanName.ARTICLE_RAG_INGEST, context=ctx) as span:
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
                span.record_exception(exc)
                span.set_status(StatusCode.ERROR, type(exc).__name__)
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
                    context={"span": SpanName.ARTICLE_RAG_INGEST.value, "content_chars": content_chars},
                    traceback=format_filtered_exc(exc),
                    correlation_id=get_correlation_id() or None,
                ))
                # RateLimitExhausted means the embedding provider's daily
                # request cap (RPD) is spent and won't recover this run — every
                # remaining article would fail the same way. Re-raise so the
                # pipeline can trip its circuit breaker and stop dispatching
                # RAG for the rest of the run. All other exceptions stay
                # swallowed (this article failed; the next one is independent).
                if isinstance(exc, RateLimitExhausted):
                    raise
