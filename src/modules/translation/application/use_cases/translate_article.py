from dataclasses import dataclass
from typing import Dict, List, Optional
from uuid import UUID

from src.shared.logging import get_logger
from src.modules.intelligence.domain.services import LLMService
from src.modules.translation.domain.repositories import TranslationRepository, TagTranslationRepository
from src.modules.translation.domain.entities import Translation

logger = get_logger(__name__)


# Language names for prompt
LANGUAGE_NAMES = {
    "zh-TW": "Traditional Chinese (Taiwan)",
    "zh-CN": "Simplified Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
}


# Translation prompt template
TRANSLATION_PROMPT = """You are a professional translator. Translate the following article analysis from English to {target_language}.

Only translate the content, do not add any explanations or additional text.
Keep the same format and structure — use the exact section headers below.
If any field is not applicable or empty, keep it empty.

Summary:
{summary}

Pain Points:
{pain_points}

Insights:
{insights}

Innovations:
{innovations}

Translation (use the same section headers: Summary, Pain Points, Insights, Innovations):"""

# Tag translation prompt template
TAG_TRANSLATION_PROMPT = """You are a professional translator. Translate the following tag names from English to {target_language}.
These are technical tags used in a research article classification system.
Keep translations concise and natural in the target language.
IMPORTANT: Do NOT translate words or phrases that are fully uppercase (e.g., AI, IoT, IIoT, BIM, VR) — keep them as-is.

Tags (one per line):
{tags}

Return the translated tags, one per line, in the same order. Do not add any other text."""

# Tag group display_name translation prompt template
GROUP_TRANSLATION_PROMPT = """You are a professional translator. Translate the following tag group display names from English to {target_language}.
These are category headings for a research article classification system.
Keep translations concise and natural.
IMPORTANT: Do NOT translate words or phrases that are fully uppercase or proper nouns (e.g., Digital Twin, AI, IoT, Industry 4.0) — keep them as-is.

Groups (one per line):
{groups}

Return the translated group names, one per line, in the same order. Do not add any other text."""


@dataclass
class TranslationResult:
    """Result of translation operation."""
    analysis_id: UUID
    language: str
    summary: Optional[str]
    pain_points: Optional[str]
    insights: Optional[str]
    innovations: Optional[str]
    success: bool


class TranslateArticleUseCase:
    """
    Application use case for translating article analysis content.

    Depends on:
    - LLMService: for translating content via LLM
    - TranslationRepository: for persisting translations
    """

    def __init__(
        self,
        llm_service: LLMService,
        translation_repository: TranslationRepository,
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
    ) -> TranslationResult:
        """
        Translate article analysis to target language.

        Returns TranslationResult with translated content or failure flag.
        """
        # Check if translation already exists
        if self._translation_repository.exists(analysis_id, target_language):
            logger.info("translation_already_exists", analysis_id=str(analysis_id), language=target_language)
            existing = self._translation_repository.find_by_analysis_id_and_language(analysis_id, target_language)
            if existing:
                return TranslationResult(
                    analysis_id=analysis_id,
                    language=target_language,
                    summary=existing.summary,
                    pain_points=existing.pain_points,
                    insights=existing.insights,
                    innovations=existing.innovations,
                    success=True,
                )

        # Translate using LLM
        translated = self._translate_with_llm(
            summary, pain_points, insights, innovations, target_language
        )

        if translated is None:
            logger.error("translation_llm_failed", analysis_id=str(analysis_id), language=target_language)
            return TranslationResult(
                analysis_id=analysis_id,
                language=target_language,
                summary=None,
                pain_points=None,
                insights=None,
                innovations=None,
                success=False,
            )

        # Save translation
        translation = Translation(
            analysis_id=analysis_id,
            language=target_language,
            summary=translated["summary"],
            pain_points=translated["pain_points"],
            insights=translated["insights"],
            innovations=translated["innovations"],
        )

        try:
            self._translation_repository.save(translation)
            logger.info("translation_saved", analysis_id=str(analysis_id), language=target_language)
        except Exception as e:
            logger.error("translation_save_failed", analysis_id=str(analysis_id), error=str(e))
            return TranslationResult(
                analysis_id=analysis_id,
                language=target_language,
                summary=None,
                pain_points=None,
                insights=None,
                innovations=None,
                success=False,
            )

        return TranslationResult(
            analysis_id=analysis_id,
            language=target_language,
            summary=translated["summary"],
            pain_points=translated["pain_points"],
            insights=translated["insights"],
            innovations=translated["innovations"],
            success=True,
        )

    def _translate_with_llm(
        self,
        summary: Optional[str],
        pain_points: Optional[str],
        insights: Optional[str],
        innovations: Optional[str],
        target_language: str,
    ) -> Optional[dict]:
        """Translate content using LLM service."""
        target_lang_name = LANGUAGE_NAMES.get(target_language, target_language)

        prompt = TRANSLATION_PROMPT.format(
            target_language=target_lang_name,
            summary=summary or "(empty)",
            pain_points=pain_points or "(empty)",
            insights=insights or "(empty)",
            innovations=innovations or "(empty)",
        )

        try:
            translated_text = self._llm_service.translate("", prompt)
            if translated_text is None:
                return None

            return self._parse_sections(translated_text)
        except Exception as e:
            logger.error("llm_translation_error", error=str(e))
            return None

    @staticmethod
    def _parse_sections(text: str) -> dict:
        """Parse translated text into sections by header."""
        import re
        sections = {"summary": "", "pain_points": "", "insights": "", "innovations": ""}
        header_map = {
            "summary": "summary",
            "pain points": "pain_points",
            "insights": "insights",
            "innovations": "innovations",
        }
        # Split on section headers (case-insensitive)
        parts = re.split(r'\n(?=(?:Summary|Pain Points|Insights|Innovations)\s*[:：]\s*)', text, flags=re.IGNORECASE)
        for part in parts:
            for header, key in header_map.items():
                if re.match(rf'^{header}\s*[:：]', part, re.IGNORECASE):
                    content = re.sub(rf'^{header}\s*[:：]\s*', '', part, flags=re.IGNORECASE).strip()
                    sections[key] = content
                    break
        return sections


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

        target_lang_name = LANGUAGE_NAMES.get(language, language)
        prompt = TAG_TRANSLATION_PROMPT.format(
            target_language=target_lang_name,
            tags="\n".join(tag_names),
        )

        translated_text = self._llm_service.translate("", prompt)
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

        target_lang_name = LANGUAGE_NAMES.get(language, language)
        prompt = GROUP_TRANSLATION_PROMPT.format(
            target_language=target_lang_name,
            groups="\n".join(display_names),
        )

        translated_text = self._llm_service.translate("", prompt)
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