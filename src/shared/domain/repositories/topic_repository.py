from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.shared.domain import Topic


class TopicRepository(ABC):

    @abstractmethod
    def list_active(self) -> List[Topic]:
        """Return all active topics ordered by sort_order."""

    @abstractmethod
    def find_by_id(self, topic_id: UUID) -> Optional[Topic]:
        """Return a single Topic or None."""
