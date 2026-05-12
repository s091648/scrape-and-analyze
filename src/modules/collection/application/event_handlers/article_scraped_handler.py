from src.modules.collection.application.events import ArticleScrapedEvent
from src.modules.collection.application.use_cases import ArticleOutcome, PipelineStats, ProcessScrapedArticleUseCase


class ArticleScrapedHandler:
    def __init__(
        self,
        use_case: ProcessScrapedArticleUseCase,
        pipeline_stats: PipelineStats,
    ) -> None:
        self._use_case = use_case
        self._pipeline_stats = pipeline_stats

    def handle(self, event: ArticleScrapedEvent) -> bool:
        outcome = self._use_case.execute(event)
        self._pipeline_stats.record(event.source, outcome)
        return outcome != ArticleOutcome.FAILED