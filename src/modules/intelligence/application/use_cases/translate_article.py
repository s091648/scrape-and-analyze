from typing import Dict, Optional
from uuid import UUID

from src.shared.logging import get_logger
from src.modules.intelligence.domain.services import LLMService
from src.modules.intelligence.domain.repositories import AnalysisTranslationRepository, TagTranslationRepository
from src.modules.intelligence.domain.entities import AnalysisTranslation
from src.modules.intelligence.domain.value_objects import (
    ArticleTranslationPrompt,
    TagTranslationPrompt,
    GroupTranslationPrompt,
    AnalysisTranslationContent,
    AnalysisTranslationResult,
)

logger = get_logger(__name__)


class TranslateArticleUseCase:
    """
    Application use case for translating article analysis content.

    Depends on:
    - LLMService: for translating content via LLM
    - AnalysisTranslationRepository: for persisting translations
    """

    def __init__(
        self,
        llm_service: LLMService,
        translation_repository: AnalysisTranslationRepository,
    ) -> None:
        self._llm_service = llm_service
        self._translation_repository = translation_repository

    def execute(
        self,
        analysis_id: UUID,
        summary: Optional[str],
        pain_points: Optional[str],
        insights: Optional[str],
        innovations: Optional[str],
        target_language: str,
    ) -> AnalysisTranslationResult:
        """
        Translate article analysis to target language.

        Returns AnalysisTranslationResult with translated content or failure flag.
        """
        # Check if translation already exists
        if self._translation_repository.exists(analysis_id, target_language):
            logger.info("translation_already_exists", analysis_id=str(analysis_id), language=target_language)
            existing = self._translation_repository.find_by_analysis_id_and_language(analysis_id, target_language)
            if existing:
                return AnalysisTranslationResult(
                    analysis_id=analysis_id,
                    language=target_language,
                    content=AnalysisTranslationContent(
                        summary=existing.summary,
                        pain_points=existing.pain_points,
                        insights=existing.insights,
                        innovations=existing.innovations,
                    ),
                    success=True,
                )

        # Build prompt via value object
        prompt = ArticleTranslationPrompt().render(
            target_language=target_language,
            summary=summary or "(empty)",
            pain_points=pain_points or "(empty)",
            insights=insights or "(empty)",
            innovations=innovations or "(empty)",
        )

        # Translate using LLM
        translated = self._call_llm(prompt)

        if translated is None:
            logger.error("translation_llm_failed", analysis_id=str(analysis_id), language=target_language)
            return AnalysisTranslationResult(
                analysis_id=analysis_id,
                language=target_language,
                content=AnalysisTranslationContent(
                    summary=None,
                    pain_points=None,
                    insights=None,
                    innovations=None,
                ),
                success=False,
            )

        # Save translation
        translation = AnalysisTranslation(
            analysis_id=analysis_id,
            language=target_language,
            summary=translated.summary,
            pain_points=translated.pain_points,
            insights=translated.insights,
            innovations=translated.innovations,
        )

        try:
            self._translation_repository.save(translation)
            logger.info("translation_saved", analysis_id=str(analysis_id), language=target_language)
        except Exception as e:
            logger.error("translation_save_failed", analysis_id=str(analysis_id), error=str(e))
            return AnalysisTranslationResult(
                analysis_id=analysis_id,
                language=target_language,
                content=AnalysisTranslationContent(
                    summary=None,
                    pain_points=None,
                    insights=None,
                    innovations=None,
                ),
                success=False,
            )

        return AnalysisTranslationResult(
            analysis_id=analysis_id,
            language=target_language,
            content=translated,
            success=True,
        )

    def _call_llm(self, prompt: ArticleTranslationPrompt) -> Optional[AnalysisTranslationContent]:
        """Translate content using LLM service."""
        try:
            translated_text = self._llm_service.translate("", prompt.content)
            if translated_text is None:
                return None
            return self._parse_sections(translated_text)
        except Exception as e:
            logger.error("llm_translation_error", error=str(e))
            return None

    @staticmethod
    def _parse_sections(text: str) -> AnalysisTranslationContent:
        """Parse translated text into sections by header."""
        import re
        header_map = {
            "summary": "summary",
            "pain points": "pain_points",
            "insights": "insights",
            "innovations": "innovations",
        }
        parts = re.split(r'\n(?=(?:Summary|Pain Points|Insights|Innovations)\s*[:：]\s*)', text, flags=re.IGNORECASE)
        fields = {"summary": "", "pain_points": "", "insights": "", "innovations": ""}
        for part in parts:
            for header, key in header_map.items():
                if re.match(rf'^{header}\s*[:：]', part, re.IGNORECASE):
                    fields[key] = re.sub(rf'^{header}\s*[:：]\s*', '', part, flags=re.IGNORECASE).strip()
                    break
        return AnalysisTranslationContent(**fields)


class TranslateTagsUseCase:
    """Use case for batch-translating tag names and tag group display names."""

    def __init__(
        self,
        llm_service: LLMService,
        tag_translation_repository: TagTranslationRepository,
    ) -> None:
        self._llm_service = llm_service
        self._tag_repo = tag_translation_repository

    def translate_tags(self, language: str, limit: int = 50) -> Dict[str, int]:
        """Translate tag names that are missing translations."""
        tags = self._tag_repo.find_tags_without_translation(language, limit)
        if not tags:
            logger.info("no_tags_to_translate", language=language)
            return {"total": 0, "success": 0, "failed": 0}

        logger.info("tags_to_translate", count=len(tags), language=language)

        tag_names = [t["name"] for t in tags]
        tag_ids = [t["tag_id"] for t in tags]

        prompt = TagTranslationPrompt().render(
            target_language=language,
            tags=tag_names,
        )

        translated_text = self._llm_service.translate("", prompt.content)
        if translated_text is None:
            logger.error("tag_translation_llm_failed", language=language)
            return {"total": len(tags), "success": 0, "failed": len(tags)}

        translated_lines = [line.strip() for line in translated_text.strip().split("\n") if line.strip()]

        success, failed = 0, 0
        for i, tag_id in enumerate(tag_ids):
            if i < len(translated_lines):
                try:
                    self._tag_repo.save_tag_translation(tag_id, language, translated_lines[i])
                    success += 1
                except Exception as e:
                    logger.warning("tag_translation_save_failed", tag_id=str(tag_id), error=str(e))
                    failed += 1
            else:
                failed += 1

        logger.info("tag_translation_batch_completed", total=len(tags), success=success, failed=failed)
        return {"total": len(tags), "success": success, "failed": failed}

    def translate_groups(self, language: str, limit: int = 50) -> Dict[str, int]:
        """Translate tag group display names that are missing translations."""
        groups = self._tag_repo.find_groups_without_translation(language, limit)
        if not groups:
            logger.info("no_groups_to_translate", language=language)
            return {"total": 0, "success": 0, "failed": 0}

        logger.info("groups_to_translate", count=len(groups), language=language)

        display_names = [g["display_name"] for g in groups]
        group_ids = [g["id"] for g in groups]

        prompt = GroupTranslationPrompt().render(
            target_language=language,
            groups=display_names,
        )

        translated_text = self._llm_service.translate("", prompt.content)
        if translated_text is None:
            logger.error("group_translation_llm_failed", language=language)
            return {"total": len(groups), "success": 0, "failed": len(groups)}

        translated_lines = [line.strip() for line in translated_text.strip().split("\n") if line.strip()]

        success, failed = 0, 0
        for i, group_id in enumerate(group_ids):
            if i < len(translated_lines):
                try:
                    self._tag_repo.save_group_translation(group_id, language, translated_lines[i])
                    success += 1
                except Exception as e:
                    logger.warning("group_translation_save_failed", group_id=str(group_id), error=str(e))
                    failed += 1
            else:
                failed += 1

        logger.info("group_translation_batch_completed", total=len(groups), success=success, failed=failed)
        return {"total": len(groups), "success": success, "failed": failed}
