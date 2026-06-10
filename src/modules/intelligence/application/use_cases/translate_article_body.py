from typing import Optional
from uuid import UUID

from src.shared.logging import get_logger
from src.modules.intelligence.domain.services import LLMService
from src.modules.intelligence.domain.repositories.article_translation_repository import ArticleTranslationRepository
from src.modules.intelligence.domain.value_objects.translation_prompt import ArticleBodyTranslationPrompt
from src.modules.intelligence.domain.value_objects.analyses_translation_content import (
    ArticleBodyTranslationContent,
    ArticleBodyTranslationResult,
)

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

        Returns ArticleBodyTranslationResult with translated fields or failure flag.
        """
        if self._translation_repository.exists(article_id, target_language):
            logger.info("article_body_translation_exists", article_id=str(article_id), language=target_language)
            existing = self._translation_repository.find_by_article_id_and_language(article_id, target_language)
            if existing:
                return ArticleBodyTranslationResult(
                    article_id=article_id,
                    language=target_language,
                    content=existing,
                    success=True,
                )

        rendered = self._prompt.render(
            target_language=target_language,
            title=title or "(empty)",
            content=content or "(empty)",
        )

        translated_text = self._call_llm(rendered.content)
        if translated_text is None:
            logger.error("article_body_translation_llm_failed", article_id=str(article_id), language=target_language)
            return ArticleBodyTranslationResult(
                article_id=article_id,
                language=target_language,
                content=ArticleBodyTranslationContent(title=None, content=None),
                success=False,
            )

        translated_title, translated_content = ArticleBodyTranslationPrompt.parse_response(translated_text)

        if translated_title is None and translated_content is None:
            logger.error("article_body_translation_parse_failed", article_id=str(article_id), language=target_language)
            return ArticleBodyTranslationResult(
                article_id=article_id,
                language=target_language,
                content=ArticleBodyTranslationContent(title=None, content=None),
                success=False,
            )

        try:
            self._translation_repository.save(
                article_id=article_id,
                language=target_language,
                title=translated_title or "",
                content=translated_content,
            )
            logger.info("article_body_translation_saved", article_id=str(article_id), language=target_language)
        except Exception as e:
            logger.error("article_body_translation_save_failed", article_id=str(article_id), error=str(e))
            return ArticleBodyTranslationResult(
                article_id=article_id,
                language=target_language,
                content=ArticleBodyTranslationContent(title=None, content=None),
                success=False,
            )

        return ArticleBodyTranslationResult(
            article_id=article_id,
            language=target_language,
            content=ArticleBodyTranslationContent(title=translated_title, content=translated_content),
            success=True,
        )

    def _call_llm(self, prompt_content: str) -> Optional[str]:
        try:
            return self._llm_service.translate("", prompt_content)
        except Exception as e:
            logger.error("llm_article_body_translation_error", error=str(e))
            return None
