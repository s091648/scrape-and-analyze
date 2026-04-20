from src.shared.domain.entities import Article
from src.shared.logging import get_logger
from src.modules.intelligence.domain.entities import Analysis
from src.modules.intelligence.domain.repositories import AnalysisRepository
from src.modules.intelligence.domain.services import LLMService

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
        result = self._llm_service.analyze(content)

        if result is None:
            logger.error("llm_analysis_failed", article_id=str(article.id))
            return False

        analysis_content, analysis_metadata = result
        analysis = Analysis(
            article_id=article.id,
            analysis_content=analysis_content,
            analysis_metadata=analysis_metadata,
        )

        try:
            self._analysis_repository.save(analysis)
        except Exception as e:
            logger.error("analysis_save_failed", article_id=str(article.id), error=str(e))
            return False

        logger.info(
            "analysis_completed",
            article_id=str(article.id),
            model=analysis_metadata.model_used,
            input_tokens=analysis_metadata.input_tokens,
            output_tokens=analysis_metadata.output_tokens,
        )
        return True
