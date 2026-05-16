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
        return AnalysisPrompt()

    def article_translation_prompt(self) -> ArticleTranslationPrompt:
        return ArticleTranslationPrompt()

    def tag_translation_prompt(self) -> TagTranslationPrompt:
        return TagTranslationPrompt()

    def group_translation_prompt(self) -> GroupTranslationPrompt:
        return GroupTranslationPrompt()
