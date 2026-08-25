from abc import ABC, abstractmethod
from typing import List, Optional, Protocol
from uuid import UUID

from src.shared.domain.entities import Topic


class TopicRepository(ABC):
    """Abstract repository interface for Topic lookup queries."""

    @abstractmethod
    def list_active(self) -> List[Topic]:
        """Return all active topics ordered by sort_order."""

    @abstractmethod
    def find_by_id(self, topic_id: UUID) -> Optional[Topic]:
        """Return a single Topic or None."""


class AsyncTopicRepository(Protocol):
    """024-async-pipeline-refactor: async sibling. TopicRepository/
    SqlAlchemyTopicRepository are also used by build_weekly_pipeline()
    (out of scope) — this Protocol and its impl are new, separate code,
    never touching the shared sync class. See contracts/async-repository-ports.md.
    """

    async def list_active(self) -> List[Topic]:
        ...

    async def find_by_id(self, topic_id: UUID) -> Optional[Topic]:
        ...
