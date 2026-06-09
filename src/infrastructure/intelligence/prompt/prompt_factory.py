from src.modules.intelligence.domain.factories import PromptFactory
from src.modules.intelligence.domain.value_objects import (
    AnalysisPrompt,
    ArticleTranslationPrompt,
    TagTranslationPrompt,
    GroupTranslationPrompt,
)


class ConcretePromptFactory(PromptFactory):
    """Creates the default built-in prompt value objects for the intelligence pipeline."""

    def analysis_prompt(self) -> AnalysisPrompt:
        """Return the default analysis prompt value object."""
        return AnalysisPrompt()

    def article_translation_prompt(self) -> ArticleTranslationPrompt:
        """Return the default article translation prompt value object."""
        return ArticleTranslationPrompt()

    def tag_translation_prompt(self) -> TagTranslationPrompt:
        """Return the default tag translation prompt value object."""
        return TagTranslationPrompt()

    def group_translation_prompt(self) -> GroupTranslationPrompt:
        """Return the default tag group translation prompt value object."""
        return GroupTranslationPrompt()
