from src.modules.collection.application.events import ArticleScrapedEvent
from src.modules.collection.application.use_cases import ArticleOutcome, PipelineStats, ProcessScrapedArticleUseCase
from src.shared.application.events import ArticleProcessedEvent
from src.shared.application.ports import EventBus


class ArticleScrapedHandler:
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
        outcome, article = self._use_case.execute(event)
        self._pipeline_stats.record(event.source, outcome)

        if article is not None:
            self._event_bus.publish(ArticleProcessedEvent(article=article))

        return outcome != ArticleOutcome.FAILED
