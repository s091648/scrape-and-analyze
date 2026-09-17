from uuid import UUID

from src.shared.logging import get_logger
from src.modules.intelligence.domain.services import LLMService, AsyncLLMService
from src.modules.intelligence.domain.repositories.article_translation_repository import ArticleTranslationRepository
from src.modules.intelligence.domain.value_objects.translation_prompt import ArticleBodyTranslationPrompt
from src.modules.intelligence.domain.value_objects.analyses_translation_content import (
    ArticleBodyTranslationContent,
    ArticleBodyTranslationResult,
)
from .exceptions import LLMTranslationError, TranslationParseError

logger = get_logger(__name__)


class TranslateArticleBodyUseCase:
    """Translate article title and content into a target language."""

    def __init__(
        self,
        llm_service: LLMService,
        translation_repository: ArticleTranslationRepository,
        prompt: ArticleBodyTranslationPrompt,
    ) -> None:
        self._llm_service = llm_service
        self._translation_repository = translation_repository
        self._prompt = prompt

    def execute(
        self,
        article_id: UUID,
        title: str,
        content: str,
        target_language: str,
    ) -> ArticleBodyTranslationResult:
        """Translate article title and content to target_language.

        Returns ArticleBodyTranslationResult on success — raises on any
        failure (all LLM providers exhausted, unparseable response, or
        persistence failing). The caller is responsible for catching,
        logging, and publishing a TranslationFailedEvent.
        """
        if self._translation_repository.exists(article_id, target_language):
            logger.info("article_body_translation_exists", article_id=str(article_id), language=target_language)
            existing = self._translation_repository.find_by_article_id_and_language(article_id, target_language)
            if existing:
                return ArticleBodyTranslationResult(
                    article_id=article_id,
                    language=target_language,
                    content=existing,
                )

        rendered = self._prompt.render(
            target_language=target_language,
            title=title or "(empty)",
            content=content or "(empty)",
        )

        translated_text = self._llm_service.translate("", rendered.content)
        if translated_text is None:
            raise LLMTranslationError("LLM returned no translation output")

        translated_title, translated_content = ArticleBodyTranslationPrompt.parse_response(translated_text)

        if translated_title is None and translated_content is None:
            raise TranslationParseError(
                f"Could not parse title/content from LLM response: {translated_text[:500]!r}"
            )

        self._translation_repository.save(
            article_id=article_id,
            language=target_language,
            title=translated_title or "",
            content=translated_content,
        )
        logger.info("article_body_translation_saved", article_id=str(article_id), language=target_language)

        return ArticleBodyTranslationResult(
            article_id=article_id,
            language=target_language,
            content=ArticleBodyTranslationContent(title=translated_title, content=translated_content),
        )


class AsyncTranslateArticleBodyUseCase:
    """024-async-pipeline-refactor: async sibling of TranslateArticleBodyUseCase
    — new, separate class (also constructed by the out-of-scope standalone
    translate CLI job via build_translation_pipeline()). Same logic,
    `async def`/`await` throughout, uses AsyncArticleTranslationRepository."""

    def __init__(
        self,
        llm_service: AsyncLLMService,
        translation_repository: ArticleTranslationRepository,
        prompt: ArticleBodyTranslationPrompt,
    ) -> None:
        self._llm_service = llm_service
        self._translation_repository = translation_repository
        self._prompt = prompt

    async def execute(
        self,
        article_id: UUID,
        title: str,
        content: str,
        target_language: str,
    ) -> ArticleBodyTranslationResult:
        if await self._translation_repository.exists(article_id, target_language):
            logger.info("article_body_translation_exists", article_id=str(article_id), language=target_language)
            existing = await self._translation_repository.find_by_article_id_and_language(article_id, target_language)
            if existing:
                return ArticleBodyTranslationResult(
                    article_id=article_id,
                    language=target_language,
                    content=existing,
                )

        rendered = self._prompt.render(
            target_language=target_language,
            title=title or "(empty)",
            content=content or "(empty)",
        )

        translated_text = await self._llm_service.translate("", rendered.content)
        if translated_text is None:
            raise LLMTranslationError("LLM returned no translation output")

        translated_title, translated_content = ArticleBodyTranslationPrompt.parse_response(translated_text)

        if translated_title is None and translated_content is None:
            raise TranslationParseError(
                f"Could not parse title/content from LLM response: {translated_text[:500]!r}"
            )

        await self._translation_repository.save(
            article_id=article_id,
            language=target_language,
            title=translated_title or "",
            content=translated_content,
        )
        logger.info("article_body_translation_saved", article_id=str(article_id), language=target_language)

        return ArticleBodyTranslationResult(
            article_id=article_id,
            language=target_language,
            content=ArticleBodyTranslationContent(title=translated_title, content=translated_content),
        )
