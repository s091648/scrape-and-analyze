from src.shared.logging import get_logger
from src.modules.intelligence.application.events import AnalysisCompletedEvent
from src.modules.intelligence.application.use_cases import TranslateArticleUseCase, TranslateTagsUseCase

logger = get_logger(__name__)


class AnalysisCompletedHandler:
    """Translates article analysis and tags after analysis completes."""

    def __init__(
        self,
        translate_article_uc: TranslateArticleUseCase,
        translate_tags_uc: TranslateTagsUseCase,
        target_languages: list[str] | None = None,
        session_rollback_fn=None,
    ) -> None:
        self._translate_article_uc = translate_article_uc
        self._translate_tags_uc = translate_tags_uc
        self._target_languages = target_languages or ["zh-TW"]
        self._session_rollback = session_rollback_fn

    def handle(self, event: AnalysisCompletedEvent) -> None:
        for lang in self._target_languages:
            try:
                result = self._translate_article_uc.execute(
                    analysis_id=event.analysis_id,
                    summary=event.summary,
                    pain_points=event.pain_points,
                    insights=event.insights,
                    innovations=event.innovations,
                    target_language=lang,
                )
                if result.success:
                    logger.info("auto_translation_completed", analysis_id=str(event.analysis_id), language=lang)
                else:
                    logger.warning("auto_translation_failed", analysis_id=str(event.analysis_id), language=lang)
            except Exception as e:
                logger.error("auto_translation_error", analysis_id=str(event.analysis_id), language=lang, error=str(e))
                self._try_rollback()

            try:
                tag_result = self._translate_tags_uc.translate_tags(lang, limit=50)
                if tag_result["failed"] > 0:
                    logger.warning("auto_tag_translation_partial", language=lang, failed=tag_result["failed"])
            except Exception as e:
                logger.error("auto_tag_translation_error", language=lang, error=str(e))
                self._try_rollback()

            try:
                group_result = self._translate_tags_uc.translate_groups(lang, limit=50)
                if group_result["failed"] > 0:
                    logger.warning("auto_group_translation_partial", language=lang, failed=group_result["failed"])
            except Exception as e:
                logger.error("auto_group_translation_error", language=lang, error=str(e))
                self._try_rollback()

    def _try_rollback(self) -> None:
        if self._session_rollback:
            try:
                self._session_rollback()
            except Exception:
                pass
