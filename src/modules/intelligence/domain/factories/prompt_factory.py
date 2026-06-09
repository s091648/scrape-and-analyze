from abc import ABC, abstractmethod

from src.modules.intelligence.domain.value_objects import (
    AnalysisPrompt,
    ArticleTranslationPrompt,
    TagTranslationPrompt,
    GroupTranslationPrompt,
)


class PromptFactory(ABC):
    """Domain interface for creating prompt value objects used in the intelligence pipeline."""

    @abstractmethod
    def analysis_prompt(self) -> AnalysisPrompt:
        """Create an analysis prompt value object."""
        ...

    @abstractmethod
    def article_translation_prompt(self) -> ArticleTranslationPrompt:
        """Create an article translation prompt value object."""
        ...

    @abstractmethod
    def tag_translation_prompt(self) -> TagTranslationPrompt:
        """Create a tag translation prompt value object."""
        ...

    @abstractmethod
    def group_translation_prompt(self) -> GroupTranslationPrompt:
        """Create a tag group translation prompt value object."""
        ...
