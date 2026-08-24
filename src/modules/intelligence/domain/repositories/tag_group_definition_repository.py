from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Protocol
from uuid import UUID


@dataclass
class TagGroupDefinitionData:
    """Data transfer object carrying tag group definition fields."""
    name: str
    display_name: str
    description: Optional[str]


class TagGroupDefinitionRepository(ABC):
    """Abstract repository interface for TagGroupDefinition persistence."""

    @abstractmethod
    def find_by_topic_id(self, topic_id: UUID) -> List[TagGroupDefinitionData]:
        """Return all TagGroupDefinitions for the given topic, ordered by sort_order."""
        ...

    @abstractmethod
    def upsert(
        self,
        name: str,
        display_name: str,
        topic_id: UUID,
        description: Optional[str] = None,
        embedding: Optional[List[float]] = None,
    ) -> None:
        """Insert a TagGroupDefinition if it does not already exist for this topic.
        If embedding is provided and the row already exists with no embedding, update it."""
        ...


class AsyncTagGroupDefinitionRepository(Protocol):
    """024-async-pipeline-refactor: async sibling — full method parity, both
    methods are called by AnalyzeArticleUseCase."""

    async def find_by_topic_id(self, topic_id: UUID) -> List[TagGroupDefinitionData]:
        ...

    async def upsert(
        self,
        name: str,
        display_name: str,
        topic_id: UUID,
        description: Optional[str] = None,
        embedding: Optional[List[float]] = None,
    ) -> None:
        ...