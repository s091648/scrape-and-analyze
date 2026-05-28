from src.shared.application.events import ArticleProcessedEvent
from src.shared.application.ports import EventBus
from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase, AnalysisResult
from src.modules.intelligence.application.events import AnalysisCompletedEvent, AnalysisFailedEvent


class ArticleProcessedHandler:
    def __init__(self, use_case: AnalyzeArticleUseCase, event_bus: EventBus) -> None:
        self._use_case = use_case
        self._event_bus = event_bus

    def handle(self, event: ArticleProcessedEvent) -> None:
        result = self._use_case.execute(event.article)

        if result.success:
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
            self._event_bus.publish(AnalysisFailedEvent(
                article_id=result.article_id,
                article_url=result.article_url,
                exception_type=result.exception_type,
                exception_message=result.exception_message,
            ))
