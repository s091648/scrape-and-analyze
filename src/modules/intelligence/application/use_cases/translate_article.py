from typing import Optional
from uuid import UUID

from src.shared.logging import get_logger
from src.modules.intelligence.domain.services import LLMService, AsyncLLMService
from src.modules.intelligence.domain.repositories import AnalysesTranslationRepository
from src.modules.intelligence.domain.entities import AnalysesContent
from src.modules.intelligence.domain.value_objects import (
    ArticleTranslationPrompt,
    AnalysesTranslationContent,
    AnalysesTranslationResult,
)
from .exceptions import LLMTranslationError, TranslationParseError

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

        Returns AnalysesTranslationResult on success — raises on any failure
        (all LLM providers exhausted, unparseable response, or persistence
        failing). The caller is responsible for catching, logging, and
        publishing a TranslationFailedEvent.
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
        translated_text = self._llm_service.translate("", rendered.content)
        if translated_text is None:
            raise LLMTranslationError("LLM returned no translation output")
        translated = self._parse_sections(translated_text)
        self._validate_parsed(translated, translated_text)

        # Save translation
        translation = AnalysesContent(
            analysis_id=analysis_id,
            language=target_language,
            summary=translated.summary,
            pain_points=translated.pain_points,
            insights=translated.insights,
            innovations=translated.innovations,
        )

        self._translation_repository.save(translation)
        logger.info("translation_saved", analysis_id=str(analysis_id), language=target_language)

        return AnalysesTranslationResult(
            analysis_id=analysis_id,
            language=target_language,
            content=translated,
        )

    @staticmethod
    def _validate_parsed(translated: AnalysesTranslationContent, raw_text: str) -> None:
        """Guard against _parse_sections silently returning all-empty fields when the
        LLM's response contains none of the expected headers — without this, an
        unparseable response was saved as a blank translation and reported as
        success (CodeRabbit review, 026-rate-limit-codegen PR #127)."""
        if not any([translated.summary, translated.pain_points, translated.insights, translated.innovations]):
            raise TranslationParseError(
                f"Could not parse any expected section from LLM translation response: {raw_text[:200]!r}"
            )

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


class AsyncTranslateArticleUseCase:
    """024-async-pipeline-refactor: async sibling of TranslateArticleUseCase —
    new, separate class. TranslateArticleUseCase is constructed by both
    build_collection_pipeline() (in scope) and build_translation_pipeline()
    (out of scope, the standalone `make translate` CLI job) — converting it
    in place would break the latter. Same logic, `async def`/`await`
    throughout, uses AsyncAnalysesTranslationRepository."""

    def __init__(
        self,
        llm_service: AsyncLLMService,
        translation_repository: AnalysesTranslationRepository,
        prompt: ArticleTranslationPrompt,
    ) -> None:
        self._llm_service = llm_service
        self._translation_repository = translation_repository
        self._prompt = prompt

    async def execute(
        self,
        analysis_id: UUID,
        summary: Optional[str],
        pain_points: Optional[str],
        insights: Optional[str],
        innovations: Optional[str],
        target_language: str,
    ) -> AnalysesTranslationResult:
        if await self._translation_repository.exists(analysis_id, target_language):
            logger.info("translation_already_exists", analysis_id=str(analysis_id), language=target_language)
            existing = await self._translation_repository.find_by_analysis_id_and_language(analysis_id, target_language)
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
                )

        rendered = self._prompt.render(
            target_language=target_language,
            summary=summary or "(empty)",
            pain_points=pain_points or "(empty)",
            insights=insights or "(empty)",
            innovations=innovations or "(empty)",
        )

        translated_text = await self._llm_service.translate("", rendered.content)
        if translated_text is None:
            raise LLMTranslationError("LLM returned no translation output")
        translated = TranslateArticleUseCase._parse_sections(translated_text)
        TranslateArticleUseCase._validate_parsed(translated, translated_text)

        translation = AnalysesContent(
            analysis_id=analysis_id,
            language=target_language,
            summary=translated.summary,
            pain_points=translated.pain_points,
            insights=translated.insights,
            innovations=translated.innovations,
        )

        await self._translation_repository.save(translation)
        logger.info("translation_saved", analysis_id=str(analysis_id), language=target_language)

        return AnalysesTranslationResult(
            analysis_id=analysis_id,
            language=target_language,
            content=translated,
        )
