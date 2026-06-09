from opentelemetry import trace as _otel_trace
from opentelemetry.trace import StatusCode

from src.shared.logging import get_logger
from src.modules.collection.application.events import ArticleScrapedEvent
from src.modules.collection.application.use_cases import ArticleOutcome, PipelineStats, ProcessScrapedArticleUseCase
from src.shared.application.events import ArticleProcessedEvent
from src.shared.application.ports import EventBus

logger = get_logger(__name__)


class ArticleScrapedHandler:
    """Handles ArticleScrapedEvent by delegating to ProcessScrapedArticleUseCase, recording stats, and publishing follow-up events."""

    def __init__(
        self,
        use_case: ProcessScrapedArticleUseCase,
        pipeline_stats: PipelineStats,
        event_bus: EventBus,
    ) -> None:
        self._use_case = use_case
        self._pipeline_stats = pipeline_stats
        self._event_bus = event_bus

    def handle(self, event: ArticleScrapedEvent) -> bool:
        """Process a scraped article event: dedup, persist, record outcome stats, and publish ArticleProcessedEvent on success."""
        span = _otel_trace.get_current_span()
        span.set_attribute("article.url", event.url)
        span.set_attribute("article.source", event.source)
        span.set_attribute("article.content_chars", len(event.content))
        if event.topic_id:
            span.set_attribute("article.topic_id", str(event.topic_id))
        original_source = event.metadata.get("original_source") if event.metadata else None
        if original_source:
            span.set_attribute("article.original_source", original_source)

        outcome, article = self._use_case.execute(event)
        self._pipeline_stats.record(event.source, outcome)

        span.set_attribute("article.outcome", outcome.value)
        if outcome == ArticleOutcome.FAILED:
            span.set_status(StatusCode.ERROR, "article scrape outcome: failed")
            logger.error("article_scrape_failed", url=event.url, source=event.source,
                         original_source=original_source)
        elif outcome == ArticleOutcome.DUPLICATE:
            logger.info("article_duplicate_skipped", url=event.url, source=event.source,
                        original_source=original_source)
        else:
            logger.info("article_scrape_accepted", url=event.url, source=event.source,
                        original_source=original_source)

        if article is not None:
            span.set_attribute("article.id", str(article.id))
            self._event_bus.publish(ArticleProcessedEvent(article=article))

        return outcome != ArticleOutcome.FAILED
