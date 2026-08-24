from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Protocol, Tuple
from uuid import UUID

from src.modules.intelligence.domain.entities import TagNormalizationSuggestion


@dataclass
class TagData:
    """Data transfer object carrying tag fields for domain use."""
    id: Optional[UUID]
    name: str
    tag_group_name: str  # human-readable; resolved from group_def.name in impl
    embedding: Optional[List[float]] = None


class TagRepository(ABC):
    """Abstract repository interface for Tag persistence and normalization operations."""

    @abstractmethod
    def find_by_group(self, group_name: str, topic_id: UUID) -> List[TagData]:
        """Return all tags belonging to the given group within a topic."""
        ...

    @abstractmethod
    def find_similar(
        self, embedding: List[float], group_name: str, topic_id: UUID, threshold: float
    ) -> List[Tuple[TagData, float]]:
        """Return list of (tag, cosine_similarity) pairs above threshold, sorted by similarity desc."""
        ...

    @abstractmethod
    def save(self, name: str, tag_group_name: str, embedding: List[float], topic_id: UUID) -> TagData:
        """Upsert a tag and return it with its DB-assigned id."""
        ...

    @abstractmethod
    def link_to_article(self, tag_id: UUID, article_id: UUID) -> None:
        """Add entry to article_tags; silently ignore if already linked."""
        ...

    @abstractmethod
    def save_suggestion(self, suggestion: TagNormalizationSuggestion) -> TagNormalizationSuggestion:
        """Persist a tag normalization suggestion."""
        ...

    @abstractmethod
    def list_pending_suggestions(self) -> List[TagNormalizationSuggestion]:
        """Return all pending tag normalization suggestions."""
        ...

    @abstractmethod
    def approve_suggestion(self, suggestion_id: UUID, resolved_by: UUID) -> None:
        """Re-point all article_tags from new_tag to existing_tag, delete new_tag, mark approved."""
        ...

    @abstractmethod
    def reject_suggestion(self, suggestion_id: UUID, resolved_by: UUID) -> None:
        """Mark a suggestion as rejected with the resolving user."""
        ...

    @abstractmethod
    def commit(self) -> None:
        """Flush current unit of work to the database."""
        ...


class AsyncTagRepository(Protocol):
    """024-async-pipeline-refactor: async sibling covering only what
    NormalizeTagsUseCase actually calls: find_similar, save, link_to_article,
    save_suggestion, commit, rollback. find_by_group/list_pending_suggestions/
    approve_suggestion/reject_suggestion are admin-only, used by backend
    routers, not this pipeline's per-article path."""

    async def find_similar(
        self, embedding: List[float], group_name: str, topic_id: UUID, threshold: float
    ) -> List[Tuple[TagData, float]]:
        ...

    async def save(self, name: str, tag_group_name: str, embedding: List[float], topic_id: UUID) -> TagData:
        ...

    async def link_to_article(self, tag_id: UUID, article_id: UUID) -> None:
        ...

    async def save_suggestion(self, suggestion: TagNormalizationSuggestion) -> TagNormalizationSuggestion:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...
