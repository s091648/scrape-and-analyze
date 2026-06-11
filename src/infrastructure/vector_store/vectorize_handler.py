from opentelemetry import trace as _otel_trace

from src.modules.articles.domain.services.vector_store_service import VectorStoreService
from src.shared.logging import get_logger

logger = get_logger(__name__)
_tracer = _otel_trace.get_tracer(__name__)


class VectorizeHandler:
    def __init__(self, vector_store: VectorStoreService) -> None:
        self._vector_store = vector_store

    def handle(self, event) -> None:
        article_id = str(event.article.id)
        with _tracer.start_as_current_span("article.vectorize") as span:
            span.set_attribute("article.id", article_id)
            try:
                self._vector_store.ingest(event.article)
                span.set_attribute("vectorize.success", True)
            except Exception:
                span.set_attribute("vectorize.success", False)
                logger.exception("vectorize_failed", article_id=article_id)
