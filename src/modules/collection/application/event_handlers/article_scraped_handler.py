from src.modules.collection.application.dtos import ScrapedArticleDTO
from src.modules.collection.application.use_cases import ArticleOutcome, PipelineStats, ProcessScrapedArticleUseCase


class ArticleScrapedHandler:
    def __init__(
        self,
        use_case: ProcessScrapedArticleUseCase,
        pipeline_stats: PipelineStats,
    ) -> None:
        self._use_case = use_case
        self._pipeline_stats = pipeline_stats

    def handle(self, dto: ScrapedArticleDTO) -> bool:
        outcome = self._use_case.execute(dto)
        self._pipeline_stats.record(dto.source, outcome)
        return outcome != ArticleOutcome.FAILED