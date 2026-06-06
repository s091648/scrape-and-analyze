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
    def analysis_prompt(self) -> AnalysisPrompt: ...

    @abstractmethod
    def article_translation_prompt(self) -> ArticleTranslationPrompt: ...

    @abstractmethod
    def tag_translation_prompt(self) -> TagTranslationPrompt: ...

    @abstractmethod
    def group_translation_prompt(self) -> GroupTranslationPrompt: ...
