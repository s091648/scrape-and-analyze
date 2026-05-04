from src.modules.collection.application.events import PipelineCompletedEvent
from src.infrastructure.shared.observability.otel_metrics import (
    SCRAPER_ARTICLES_NEW,
    SCRAPER_ARTICLES_DUPLICATE,
    SCRAPER_ERRORS,
)


class OtelMetricsHandler:
    def handle(self, event: PipelineCompletedEvent) -> None:
        for s in event.stats:
            attrs = {"source": s.source}
            SCRAPER_ARTICLES_NEW.add(s.new, attrs)
            SCRAPER_ARTICLES_DUPLICATE.add(s.duplicate, attrs)
            SCRAPER_ERRORS.add(s.failed, attrs)