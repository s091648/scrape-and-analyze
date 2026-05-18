from src.shared.logging import get_logger
from src.modules.intelligence.application.events import AnalysisCompletedEvent
from src.modules.intelligence.application.use_cases import TranslateArticleUseCase, TranslateTagsUseCase
from src.modules.intelligence.domain.repositories import AnalysesTranslationRepository

logger = get_logger(__name__)


class AnalysisCompletedHandler:
    """Translates article analysis and tags after analysis completes."""

    def __init__(
        self,
        translate_article_uc: TranslateArticleUseCase,
        translate_tags_uc: TranslateTagsUseCase,
        analyses_translation_repo: AnalysesTranslationRepository,
        target_languages: list[str] | None = None,
    ) -> None:
        self._translate_article_uc = translate_article_uc
        self._translate_tags_uc = translate_tags_uc
        self._analyses_translation_repo = analyses_translation_repo
        self._target_languages = target_languages or ["zh-TW"]

    def handle(self, event: AnalysisCompletedEvent) -> None:
        en_content = self._analyses_translation_repo.find_by_analysis_id_and_language(
            event.analysis_id, 'en'
        )
        if not en_content:
            logger.warning("no_english_content_found", analysis_id=str(event.analysis_id))
            return

        for lang in self._target_languages:
            try:
                result = self._translate_article_uc.execute(
                    analysis_id=event.analysis_id,
                    summary=en_content.summary,
                    pain_points=en_content.pain_points,
                    insights=en_content.insights,
                    innovations=en_content.innovations,
                    target_language=lang,
                )
                if result.success:
                    logger.info("auto_translation_completed", analysis_id=str(event.analysis_id), language=lang)
                else:
                    logger.warning("auto_translation_failed", analysis_id=str(event.analysis_id), language=lang)
            except Exception as e:
                logger.error("auto_translation_error", analysis_id=str(event.analysis_id), language=lang, error=str(e))

            try:
                tag_result = self._translate_tags_uc.translate_tags(lang, limit=50)
                if tag_result["failed"] > 0:
                    logger.warning("auto_tag_translation_partial", language=lang, failed=tag_result["failed"])
            except Exception as e:
                logger.error("auto_tag_translation_error", language=lang, error=str(e))

            try:
                group_result = self._translate_tags_uc.translate_groups(lang, limit=50)
                if group_result["failed"] > 0:
                    logger.warning("auto_group_translation_partial", language=lang, failed=group_result["failed"])
            except Exception as e:
                logger.error("auto_group_translation_error", language=lang, error=str(e))
