from opentelemetry import trace as _otel_trace

from src.shared.logging import get_logger
from src.shared.application.events import ArticleProcessedEvent
from src.shared.application.ports import EventBus
from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase, AnalysisResult
from src.modules.intelligence.application.events import AnalysisCompletedEvent, AnalysisFailedEvent

logger = get_logger(__name__)


class ArticleProcessedHandler:
    """Analyzes a newly processed article and publishes the result event."""

    def __init__(self, use_case: AnalyzeArticleUseCase, event_bus: EventBus) -> None:
        self._use_case = use_case
        self._event_bus = event_bus

    def handle(self, event: ArticleProcessedEvent) -> None:
        """Run LLM analysis on the article and emit success or failure event."""
        span = _otel_trace.get_current_span()
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
        result = self._use_case.execute(event.article)

        if result.topic_display_name:
            span.set_attribute("article.topic_display_name", result.topic_display_name)
        span.set_attribute("analysis.success", result.success)
        if result.success and result.analysis:
            meta = result.analysis.analysis_metadata
            span.set_attribute("llm.model", meta.model_used)
            span.set_attribute("llm.input_tokens", meta.input_tokens)
            span.set_attribute("llm.output_tokens", meta.output_tokens)
            span.set_attribute("analysis.id", str(result.analysis.id))
            logger.info(
                "analysis_completed",
                article_id=str(result.article_id),
                url=event.article.url,
                source=event.article.source,
                original_source=event.article.original_source,
                model=meta.model_used,
                input_tokens=meta.input_tokens,
                output_tokens=meta.output_tokens,
            )
            raw_tag_groups = tuple(
                (tg.group_name, list(tg.tags))
                for tg in (result.analysis.analysis_content.tag_groups or [])
            )
            self._event_bus.publish(AnalysisCompletedEvent(
                analysis_id=result.analysis.id,
                article_id=result.article_id,
                topic_id=event.article.topic_id,
                tag_groups=raw_tag_groups,
            ))
        else:
            if result.exception_type:
                span.set_attribute("analysis.error_type", result.exception_type)
            self._event_bus.publish(AnalysisFailedEvent(
                article_id=result.article_id,
                article_url=result.article_url,
                exception_type=result.exception_type,
                exception_message=result.exception_message,
            ))
