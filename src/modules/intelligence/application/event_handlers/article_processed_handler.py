from opentelemetry.trace import StatusCode
from shared.enums.observability import SpanName
from shared.observability.traceback_filter import format_filtered_exc
from src.infrastructure.shared.observability import get_tracer
from src.shared.logging import get_logger
from src.shared.application.events import ArticleProcessedEvent
from src.shared.application.ports import EventBus
from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
from src.modules.intelligence.application.events import AnalysisCompletedEvent, AnalysisFailedEvent

logger = get_logger(__name__)


class ArticleProcessedHandler:
    """Analyzes a newly processed article and publishes the result event."""

    def __init__(self, use_case: AnalyzeArticleUseCase, event_bus: EventBus) -> None:
        self._use_case = use_case
        self._event_bus = event_bus

    async def handle(self, event: ArticleProcessedEvent) -> None:
        """Run LLM analysis on the article and emit success or failure event.

        024-async-pipeline-refactor follow-up: owns its own span (see
        ArticleScrapedHandler.handle's docstring for why). The follow-up
        event is published after the span closes so it's a sibling under
        article.pipeline, not nested inside article.processed.handle.

        The use case raises on any failure (all LLM providers exhausted, or
        persistence failing) rather than returning a failure Result — this
        try/except is the single place that converts any such exception
        (anticipated or not) into an AnalysisFailedEvent, so a failure can
        never silently skip the FailedTask ledger.
        """
        next_event = None
        with get_tracer().start_as_current_span(SpanName.ARTICLE_PROCESSED_HANDLE) as span:
            span.set_attribute("article.id", str(event.article.id))
            span.set_attribute("article.url", event.article.url)
            span.set_attribute("article.source", event.article.source)
            if event.article.original_source:
                span.set_attribute("article.original_source", event.article.original_source)
            if event.article.title:
                span.set_attribute("article.title", event.article.title)
            if event.article.topic_id:
                span.set_attribute("article.topic_id", str(event.article.topic_id))

            logger.info(
                "article_analysis_started",
                article_id=str(event.article.id),
                url=event.article.url,
                source=event.article.source,
                original_source=event.article.original_source,
            )
            try:
                result = await self._use_case.execute(event.article)
            except Exception as e:
                span.set_attribute("analysis.success", False)
                span.set_attribute("analysis.error_type", type(e).__name__)
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, type(e).__name__)
                logger.exception(
                    "article_analysis_failed",
                    article_id=str(event.article.id),
                    error=str(e),
                    error_type=type(e).__name__,
                )
                next_event = AnalysisFailedEvent(
                    article_id=event.article.id,
                    article_url=event.article.url,
                    exception_type=type(e).__name__,
                    exception_message=str(e),
                    traceback=format_filtered_exc(e),
                )
            else:
                if result.topic_display_name:
                    span.set_attribute("article.topic_display_name", result.topic_display_name)
                span.set_attribute("analysis.success", True)
                meta = result.analysis.analysis_metadata
                span.set_attribute("llm.model", meta.model_used)
                span.set_attribute("llm.input_tokens", meta.input_tokens)
                span.set_attribute("llm.output_tokens", meta.output_tokens)
                span.set_attribute("analysis.id", str(result.analysis.id))
                # AnalyzeArticleUseCase.execute() already logs "analysis_completed"
                # with this same detail — this branch owns the span attributes and
                # next-event construction only, not a second log line.
                raw_tag_groups = tuple(
                    (tg.group_name, list(tg.tags))
                    for tg in (result.analysis.analysis_content.tag_groups or [])
                )
                next_event = AnalysisCompletedEvent(
                    analysis_id=result.analysis.id,
                    article_id=result.article_id,
                    topic_id=event.article.topic_id,
                    tag_groups=raw_tag_groups,
                )

        await self._event_bus.publish(next_event)
