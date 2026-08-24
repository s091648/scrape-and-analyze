from shared.enums.observability import SpanName
from src.infrastructure.shared.observability import get_tracer
from src.modules.collection.application.events import PipelineCompletedEvent


class OtelMetricsHandler:
    """Records pipeline completion metrics on its own OpenTelemetry span."""
    async def handle(self, event: PipelineCompletedEvent) -> None:
        """Attach pipeline duration and source count as attributes on a fresh OTel span."""
        with get_tracer().start_as_current_span(SpanName.PIPELINE_COMPLETED_METRICS_HANDLE) as span:
            span.set_attribute("pipeline.duration_seconds", event.execution.duration_seconds)
            span.set_attribute("pipeline.sources_count", len(event.stats))
