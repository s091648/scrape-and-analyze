from src.modules.intelligence.domain.value_objects import (
    AnalysisPrompt,
    ArticleTranslationPrompt,
    TagTranslationPrompt,
    GroupTranslationPrompt,
)
from src.infrastructure.intelligence.prompt.providers.base_provider import PromptProvider


class DefaultPromptProvider(PromptProvider):
    """Default prompt provider using the built-in hardcoded prompt templates."""

    def analysis_prompt(self) -> AnalysisPrompt:
        return AnalysisPrompt()

    def article_translation_prompt(self) -> ArticleTranslationPrompt:
        return ArticleTranslationPrompt()

    def tag_translation_prompt(self) -> TagTranslationPrompt:
        return TagTranslationPrompt()

    def group_translation_prompt(self) -> GroupTranslationPrompt:
        return GroupTranslationPrompt()
