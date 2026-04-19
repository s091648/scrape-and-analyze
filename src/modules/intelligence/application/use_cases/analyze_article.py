from src.shared.domain import Article
from src.shared.logging import get_logger
from src.modules.intelligence.domain import AnalysisRepository, LLMService

logger = get_logger(__name__)


class AnalyzeArticleUseCase:
    def __init__(
        self,
        llm_service: LLMService,
        analysis_repository: AnalysisRepository,
    ) -> None:
        self._llm_service = llm_service
        self._analysis_repository = analysis_repository

    def execute(self, article: Article) -> bool:
        content = article.get_analysis_content()
        analysis = self._llm_service.analyze(content)

        if analysis is None:
            logger.error("llm_analysis_failed", article_id=str(article.id))
            return False

        analysis.article_id = article.id

        try:
            self._analysis_repository.save(analysis)
        except Exception as e:
            logger.error("analysis_save_failed", article_id=str(article.id), error=str(e))
            return False

        logger.info(
            "analysis_completed",
            article_id=str(article.id),
            model=analysis.analysis_metadata.model_used,
            input_tokens=analysis.analysis_metadata.input_tokens,
            output_tokens=analysis.analysis_metadata.output_tokens,
        )
        return True
