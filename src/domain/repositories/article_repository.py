"""
Abstract repository interface for Article persistence.

Application-layer use cases depend on this interface, never on the
SQLAlchemy implementation.  The concrete implementation lives in
src/infrastructure/persistence/sqlalchemy_repos/ (Phase 7).
"""
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.domain.entities.article import ArticleEntity


class ArticleRepository(ABC):

    @abstractmethod
    def find_by_url_hash(self, url_hash: str) -> Optional[ArticleEntity]:
        """Return the article with this URL hash, or None if not found."""

    @abstractmethod
    def save(self, article: ArticleEntity) -> ArticleEntity:
        """Persist a new or updated article. Returns the saved entity (with id populated)."""

    @abstractmethod
    def has_analysis(self, article_id: UUID) -> bool:
        """Return True if an Analysis record exists for this article."""
