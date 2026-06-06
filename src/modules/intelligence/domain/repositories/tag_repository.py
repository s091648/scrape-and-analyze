from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple
from uuid import UUID

from src.modules.intelligence.domain.entities import TagNormalizationSuggestion


@dataclass
class TagData:
    id: Optional[UUID]
    name: str
    tag_group_name: str  # human-readable; resolved from group_def.name in impl
    embedding: Optional[List[float]] = None


class TagRepository(ABC):

    @abstractmethod
    def find_by_group(self, group_name: str, topic_id: UUID) -> List[TagData]:
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
        ...

    @abstractmethod
    def list_pending_suggestions(self) -> List[TagNormalizationSuggestion]:
        ...

    @abstractmethod
    def approve_suggestion(self, suggestion_id: UUID, resolved_by: UUID) -> None:
        """Re-point all article_tags from new_tag to existing_tag, delete new_tag, mark approved."""
        ...

    @abstractmethod
    def reject_suggestion(self, suggestion_id: UUID, resolved_by: UUID) -> None:
        ...

    @abstractmethod
    def commit(self) -> None:
        ...
