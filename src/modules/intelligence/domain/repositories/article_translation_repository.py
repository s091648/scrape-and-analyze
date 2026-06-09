from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.modules.intelligence.domain.value_objects.analyses_translation_content import ArticleBodyTranslationContent


class ArticleTranslationRepository(ABC):
    """Domain interface for article title/content translation persistence."""

    @abstractmethod
    def save(self, article_id: UUID, language: str, title: str, content: Optional[str]) -> None:
        """Save or update article translation (upsert on article_id + language)."""
        ...

    @abstractmethod
    def find_by_article_id_and_language(
        self, article_id: UUID, language: str
    ) -> Optional[ArticleBodyTranslationContent]:
        """Return translation for a specific article and language, or None."""
        ...

    @abstractmethod
    def exists(self, article_id: UUID, language: str) -> bool:
        """Return True if a translation exists for (article_id, language)."""
        ...

    @abstractmethod
    def find_articles_without_translation(self, language: str, limit: int) -> List[dict]:
        """Return articles missing a translation for the target language.

        Each element is a dict with keys: article_id, title, content.
        """
        ...
