from opentelemetry import trace as _otel_trace

from src.shared.application.ports import EventBus
from src.shared.logging import get_logger
from src.modules.intelligence.application.events import (
    AnalysisCompletedEvent,
    TagNormalizationCompletedEvent,
    TagNormalizationFailedEvent,
)
from src.modules.intelligence.application.use_cases import NormalizeTagsUseCase

logger = get_logger(__name__)


class TagNormalizationHandler:

    def __init__(self, use_case: NormalizeTagsUseCase, event_bus: EventBus) -> None:
        self._use_case = use_case
        self._event_bus = event_bus

    def handle(self, event: AnalysisCompletedEvent) -> None:
        span = _otel_trace.get_current_span()
        span.set_attribute("analysis.id", str(event.analysis_id))
        span.set_attribute("article.id", str(event.article_id))
        span.set_attribute("tags.group_count", len(event.tag_groups))
        span.set_attribute("tags.total_count", sum(len(tags) for _, tags in event.tag_groups))
        if event.topic_id:
            span.set_attribute("article.topic_id", str(event.topic_id))

        result = self._use_case.execute(
            analysis_id=event.analysis_id,
            article_id=event.article_id,
            tag_groups=list(event.tag_groups),
            topic_id=event.topic_id,
        )

        span.set_attribute("normalization.success", result.success)
        if result.success:
            self._event_bus.publish(TagNormalizationCompletedEvent(
                analysis_id=event.analysis_id,
                article_id=event.article_id,
            ))
        else:
            if result.exception_type:
                span.set_attribute("normalization.error_type", result.exception_type)
            self._event_bus.publish(TagNormalizationFailedEvent(
                analysis_id=event.analysis_id,
                article_id=event.article_id,
                exception_type=result.exception_type,
                exception_message=result.exception_message,
                traceback=result.traceback,
            ))
