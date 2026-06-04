from opentelemetry import trace as _otel_trace

from src.modules.collection.application.events import PipelineCompletedEvent


class OtelMetricsHandler:
    def handle(self, event: PipelineCompletedEvent) -> None:
        span = _otel_trace.get_current_span()
        span.set_attribute("pipeline.duration_seconds", event.duration_seconds)
        span.set_attribute("pipeline.sources_count", len(event.stats))
