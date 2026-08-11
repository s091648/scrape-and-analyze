from opentelemetry import trace as _otel_trace

from src.modules.collection.application.events import PipelineCompletedEvent


class OtelMetricsHandler:
    """Records pipeline completion metrics on the current OpenTelemetry span."""
    def handle(self, event: PipelineCompletedEvent) -> None:
        """Attach pipeline duration and source count as attributes on the current OTel span."""
        span = _otel_trace.get_current_span()
        span.set_attribute("pipeline.duration_seconds", event.execution.duration_seconds)
        span.set_attribute("pipeline.sources_count", len(event.stats))
