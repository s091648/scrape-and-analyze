import traceback as _tb_module

from opentelemetry import trace as _otel_trace

from src.modules.intelligence.domain.services.rag_ingestion_service import RagIngestionService
from src.modules.intelligence.application.events.rag_ingestion_failed import RagIngestionFailedEvent
from src.shared.logging import get_logger
from src.infrastructure.shared.logging import get_correlation_id

logger = get_logger(__name__)
_tracer = _otel_trace.get_tracer(__name__)


class RagIngestionHandler:
    def __init__(self, rag_ingestion_service: RagIngestionService, event_bus) -> None:
        self._rag_ingestion_service = rag_ingestion_service
        self._event_bus = event_bus

    def handle(self, event) -> None:
        article_id = event.article.id
        article_url = event.article.url
        with _tracer.start_as_current_span("article.rag_ingest") as span:
            span.set_attribute("article.id", str(article_id))
            try:
                self._rag_ingestion_service.ingest(event.article)
                span.set_attribute("rag_ingest.success", True)
            except Exception as exc:
                span.set_attribute("rag_ingest.success", False)
                logger.exception("rag_ingest_failed", article_id=str(article_id))
                self._event_bus.publish(RagIngestionFailedEvent(
                    article_id=article_id,
                    article_url=article_url,
                    exception_type=type(exc).__name__,
                    exception_message=str(exc),
                    context={"span": "article.rag_ingest"},
                    traceback=_tb_module.format_exc(),
                    correlation_id=get_correlation_id() or None,
                ))
