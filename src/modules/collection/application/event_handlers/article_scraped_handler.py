from opentelemetry.trace import StatusCode

from shared.enums.observability import SpanName
from shared.observability.traceback_filter import format_filtered_exc
from src.infrastructure.shared.observability import get_tracer
from src.shared.logging import get_logger
from src.modules.collection.application.events import ArticleSaveFailedEvent, ArticleScrapedEvent
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

    async def handle(self, event: ArticleScrapedEvent) -> bool:
        """Process a scraped article event: dedup, persist, record outcome stats, and publish ArticleProcessedEvent on success.

        024-async-pipeline-refactor follow-up: owns its own span (rather than
        relying on a bootstrap-level with_span wrapper — that mechanism was
        never ported to the async subscribe() calls). The next event is
        published AFTER the span closes so article.processed.handle becomes a
        sibling of article.scraped.handle under article.pipeline, not nested
        inside it — mirrors what with_span_deferred used to achieve via a
        publish()-monkeypatch, without needing that trick.

        The use case raises when persisting a genuinely new article fails
        (never for the DUPLICATE/DUPLICATE_NEEDS_ANALYSIS outcomes, which
        remain plain return values) — this try/except is the single place
        that converts any such exception into an ArticleSaveFailedEvent, so a
        save failure can never silently skip the FailedTask ledger.
        """
        next_event = None
        failed_event = None
        with get_tracer().start_as_current_span(SpanName.ARTICLE_SCRAPED_HANDLE) as span:
            span.set_attribute("article.url", event.url)
            span.set_attribute("article.source", event.source)
            span.set_attribute("article.content_chars", len(event.content))
            if event.topic_id:
                span.set_attribute("article.topic_id", str(event.topic_id))
            original_source = event.metadata.get("original_source") if event.metadata else None
            if original_source:
                span.set_attribute("article.original_source", original_source)

            try:
                outcome, article = await self._use_case.execute(event)
            except Exception as e:
                outcome = ArticleOutcome.FAILED
                self._pipeline_stats.record(event.source, outcome)
                span.set_attribute("article.outcome", outcome.value)
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, type(e).__name__)
                logger.exception(
                    "article_save_failed",
                    url=event.url, source=event.source,
                    error=str(e), error_type=type(e).__name__,
                )
                failed_event = ArticleSaveFailedEvent(
                    article_url=event.url,
                    exception_type=type(e).__name__,
                    exception_message=str(e),
                    traceback=format_filtered_exc(e),
                )
            else:
                self._pipeline_stats.record(event.source, outcome)
                span.set_attribute("article.outcome", outcome.value)
                if outcome == ArticleOutcome.DUPLICATE:
                    logger.info("article_duplicate_skipped", url=event.url, source=event.source,
                                original_source=original_source)
                else:
                    logger.info("article_scrape_accepted", url=event.url, source=event.source,
                                original_source=original_source)

                if article is not None:
                    span.set_attribute("article.id", str(article.id))
                    full_text = event.full_text or event.content
                    next_event = ArticleProcessedEvent(article=article, full_text=full_text)

        if failed_event is not None:
            await self._event_bus.publish(failed_event)
        elif next_event is not None:
            await self._event_bus.publish(next_event)

        return outcome != ArticleOutcome.FAILED
