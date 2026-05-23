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
        result = self._use_case.execute(
            analysis_id=event.analysis_id,
            article_id=event.article_id,
            tag_groups=list(event.tag_groups),
        )

        if result.success:
            self._event_bus.publish(TagNormalizationCompletedEvent(
                analysis_id=event.analysis_id,
                article_id=event.article_id,
            ))
        else:
            self._event_bus.publish(TagNormalizationFailedEvent(
                analysis_id=event.analysis_id,
                article_id=event.article_id,
                exception_type=result.exception_type,
                exception_message=result.exception_message,
                traceback=result.traceback,
            ))
