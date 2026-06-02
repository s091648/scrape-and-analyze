from opentelemetry import trace as _otel_trace

from shared.enums.observability import MetricLabelKey
from src.modules.collection.application.events import PipelineCompletedEvent
from src.infrastructure.shared.observability.otel_metrics import (
    SCRAPER_ARTICLES_NEW,
    SCRAPER_ARTICLES_DUPLICATE,
    SCRAPER_ERRORS,
)


class OtelMetricsHandler:
    def handle(self, event: PipelineCompletedEvent) -> None:
        span = _otel_trace.get_current_span()
        span.set_attribute("pipeline.duration_seconds", event.duration_seconds)
        span.set_attribute("pipeline.sources_count", len(event.stats))

        for s in event.stats:
            attrs = {MetricLabelKey.SOURCE: s.source}
            SCRAPER_ARTICLES_NEW.add(s.new, attrs)
            SCRAPER_ARTICLES_DUPLICATE.add(s.duplicate, attrs)
            SCRAPER_ERRORS.add(s.failed, attrs)
