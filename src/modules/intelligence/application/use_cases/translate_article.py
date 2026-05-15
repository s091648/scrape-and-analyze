from typing import Optional
from uuid import UUID

from src.shared.logging import get_logger
from src.modules.intelligence.domain.services import LLMService
from src.modules.intelligence.domain.repositories import AnalysesTranslationRepository
from src.modules.intelligence.domain.entities import AnalysesTranslation
from src.modules.intelligence.domain.value_objects import (
    ArticleTranslationPrompt,
    AnalysesTranslationContent,
    AnalysesTranslationResult,
)

logger = get_logger(__name__)


class TranslateArticleUseCase:
    """
    Application use case for translating article analysis content.

    Depends on:
    - LLMService: for translating content via LLM
    - AnalysesTranslationRepository: for persisting translations
    - ArticleTranslationPrompt: injected prompt template (infrastructure decides which one)
    """

    def __init__(
        self,
        llm_service: LLMService,
        translation_repository: AnalysesTranslationRepository,
        prompt: ArticleTranslationPrompt,
    ) -> None:
        self._llm_service = llm_service
        self._translation_repository = translation_repository
        self._prompt = prompt

    def execute(
        self,
        analysis_id: UUID,
        summary: Optional[str],
        pain_points: Optional[str],
        insights: Optional[str],
        innovations: Optional[str],
        target_language: str,
    ) -> AnalysesTranslationResult:
        """
        Translate article analysis to target language.

        Returns AnalysesTranslationResult with translated content or failure flag.
        """
        # Check if translation already exists
        if self._translation_repository.exists(analysis_id, target_language):
            logger.info("translation_already_exists", analysis_id=str(analysis_id), language=target_language)
            existing = self._translation_repository.find_by_analysis_id_and_language(analysis_id, target_language)
            if existing:
                return AnalysesTranslationResult(
                    analysis_id=analysis_id,
                    language=target_language,
                    content=AnalysesTranslationContent(
                        summary=existing.summary,
                        pain_points=existing.pain_points,
                        insights=existing.insights,
                        innovations=existing.innovations,
                    ),
                    success=True,
                )

        # Render prompt from injected template
        rendered = self._prompt.render(
            target_language=target_language,
            summary=summary or "(empty)",
            pain_points=pain_points or "(empty)",
            insights=insights or "(empty)",
            innovations=innovations or "(empty)",
        )

        # Translate using LLM
        translated = self._call_llm(rendered.content)

        if translated is None:
            logger.error("translation_llm_failed", analysis_id=str(analysis_id), language=target_language)
            return AnalysesTranslationResult(
                analysis_id=analysis_id,
                language=target_language,
                content=AnalysesTranslationContent(
                    summary=None,
                    pain_points=None,
                    insights=None,
                    innovations=None,
                ),
                success=False,
            )

        # Save translation
        translation = AnalysesTranslation(
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
            return AnalysesTranslationResult(
                analysis_id=analysis_id,
                language=target_language,
                content=AnalysesTranslationContent(
                    summary=None,
                    pain_points=None,
                    insights=None,
                    innovations=None,
                ),
                success=False,
            )

        return AnalysesTranslationResult(
            analysis_id=analysis_id,
            language=target_language,
            content=translated,
            success=True,
        )

    def _call_llm(self, prompt_content: str) -> Optional[AnalysesTranslationContent]:
        """Translate content using LLM service."""
        try:
            translated_text = self._llm_service.translate("", prompt_content)
            if translated_text is None:
                return None
            return self._parse_sections(translated_text)
        except Exception as e:
            logger.error("llm_translation_error", error=str(e))
            return None

    @staticmethod
    def _parse_sections(text: str) -> AnalysesTranslationContent:
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
        return AnalysesTranslationContent(**fields)
