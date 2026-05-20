from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID


@dataclass
class TagGroupDefinitionData:
    name: str
    display_name: str
    description: Optional[str]


class TagGroupDefinitionRepository(ABC):

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
    ) -> None:
        """Insert a TagGroupDefinition if it does not already exist for this topic."""
        ...
