from typing import Dict

from src.shared.logging import get_logger
from src.modules.intelligence.domain.services import LLMService
from src.modules.intelligence.domain.repositories import TagTranslationRepository
from src.modules.intelligence.domain.value_objects import (
    TagTranslationPrompt,
    GroupTranslationPrompt,
)

logger = get_logger(__name__)


class TranslateTagsUseCase:
    """Use case for batch-translating tag names and tag group display names."""

    def __init__(
        self,
        llm_service: LLMService,
        tag_translation_repository: TagTranslationRepository,
        tag_prompt: TagTranslationPrompt,
        group_prompt: GroupTranslationPrompt,
    ) -> None:
        self._llm_service = llm_service
        self._tag_repo = tag_translation_repository
        self._tag_prompt = tag_prompt
        self._group_prompt = group_prompt

    def translate_tags(self, language: str, limit: int = 50) -> Dict[str, int]:
        """Translate tag names that are missing translations."""
        tags = self._tag_repo.find_tags_without_translation(language, limit)
        if not tags:
            logger.info("no_tags_to_translate", language=language)
            return {"total": 0, "success": 0, "failed": 0}

        logger.info("tags_to_translate", count=len(tags), language=language)

        tag_names = [t["name"] for t in tags]
        tag_ids = [t["tag_id"] for t in tags]

        rendered = self._tag_prompt.render(target_language=language, tags=tag_names)

        translated_text = self._llm_service.translate("", rendered.content)
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
        """Translate tag group display names and descriptions that are missing translations."""
        groups = self._tag_repo.find_groups_without_translation(language, limit)
        if not groups:
            logger.info("no_groups_to_translate", language=language)
            return {"total": 0, "success": 0, "failed": 0}

        logger.info("groups_to_translate", count=len(groups), language=language)

        group_lines = [GroupTranslationPrompt.format_group(g["display_name"], g.get("description")) for g in groups]
        group_ids = [g["id"] for g in groups]

        rendered = self._group_prompt.render(target_language=language, groups=group_lines)

        translated_text = self._llm_service.translate("", rendered.content)
        if translated_text is None:
            logger.error("group_translation_llm_failed", language=language)
            return {"total": len(groups), "success": 0, "failed": len(groups)}

        translated_lines = [line.strip() for line in translated_text.strip().split("\n") if line.strip()]

        success, failed = 0, 0
        for i, group_id in enumerate(group_ids):
            if i < len(translated_lines):
                try:
                    # Parse "display_name | description" format from LLM response
                    parts = translated_lines[i].split("|", 1)
                    display_name = parts[0].strip()
                    description = parts[1].strip() if len(parts) > 1 else None
                    self._tag_repo.save_group_translation(group_id, language, display_name=display_name, description=description)
                    success += 1
                except Exception as e:
                    logger.warning("group_translation_save_failed", group_id=str(group_id), error=str(e))
                    failed += 1
            else:
                failed += 1

        logger.info("group_translation_batch_completed", total=len(groups), success=success, failed=failed)
        return {"total": len(groups), "success": success, "failed": failed}


class AsyncTranslateTagsUseCase:
    """024-async-pipeline-refactor: async sibling of TranslateTagsUseCase —
    new, separate class (also constructed by the out-of-scope standalone
    translate CLI job via build_translation_pipeline()). Same logic,
    `async def`/`await` throughout, uses AsyncTagTranslationRepository."""

    def __init__(
        self,
        llm_service,
        tag_translation_repository: TagTranslationRepository,
        tag_prompt: TagTranslationPrompt,
        group_prompt: GroupTranslationPrompt,
    ) -> None:
        self._llm_service = llm_service
        self._tag_repo = tag_translation_repository
        self._tag_prompt = tag_prompt
        self._group_prompt = group_prompt

    async def translate_tags(self, language: str, limit: int = 50) -> Dict[str, int]:
        tags = await self._tag_repo.find_tags_without_translation(language, limit)
        if not tags:
            logger.info("no_tags_to_translate", language=language)
            return {"total": 0, "success": 0, "failed": 0}

        logger.info("tags_to_translate", count=len(tags), language=language)

        tag_names = [t["name"] for t in tags]
        tag_ids = [t["tag_id"] for t in tags]

        rendered = self._tag_prompt.render(target_language=language, tags=tag_names)

        translated_text = await self._llm_service.translate("", rendered.content)
        if translated_text is None:
            logger.error("tag_translation_llm_failed", language=language)
            return {"total": len(tags), "success": 0, "failed": len(tags)}

        translated_lines = [line.strip() for line in translated_text.strip().split("\n") if line.strip()]

        success, failed = 0, 0
        for i, tag_id in enumerate(tag_ids):
            if i < len(translated_lines):
                try:
                    await self._tag_repo.save_tag_translation(tag_id, language, translated_lines[i])
                    success += 1
                except Exception as e:
                    logger.warning("tag_translation_save_failed", tag_id=str(tag_id), error=str(e))
                    failed += 1
            else:
                failed += 1

        logger.info("tag_translation_batch_completed", total=len(tags), success=success, failed=failed)
        return {"total": len(tags), "success": success, "failed": failed}

    async def translate_groups(self, language: str, limit: int = 50) -> Dict[str, int]:
        groups = await self._tag_repo.find_groups_without_translation(language, limit)
        if not groups:
            logger.info("no_groups_to_translate", language=language)
            return {"total": 0, "success": 0, "failed": 0}

        logger.info("groups_to_translate", count=len(groups), language=language)

        group_lines = [GroupTranslationPrompt.format_group(g["display_name"], g.get("description")) for g in groups]
        group_ids = [g["id"] for g in groups]

        rendered = self._group_prompt.render(target_language=language, groups=group_lines)

        translated_text = await self._llm_service.translate("", rendered.content)
        if translated_text is None:
            logger.error("group_translation_llm_failed", language=language)
            return {"total": len(groups), "success": 0, "failed": len(groups)}

        translated_lines = [line.strip() for line in translated_text.strip().split("\n") if line.strip()]

        success, failed = 0, 0
        for i, group_id in enumerate(group_ids):
            if i < len(translated_lines):
                try:
                    parts = translated_lines[i].split("|", 1)
                    display_name = parts[0].strip()
                    description = parts[1].strip() if len(parts) > 1 else None
                    await self._tag_repo.save_group_translation(group_id, language, display_name=display_name, description=description)
                    success += 1
                except Exception as e:
                    logger.warning("group_translation_save_failed", group_id=str(group_id), error=str(e))
                    failed += 1
            else:
                failed += 1

        logger.info("group_translation_batch_completed", total=len(groups), success=success, failed=failed)
        return {"total": len(groups), "success": success, "failed": failed}
