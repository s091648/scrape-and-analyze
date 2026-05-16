from abc import ABC, abstractmethod
from typing import List
from uuid import UUID


class TagTranslationRepository(ABC):
    """Domain interface for tag translation persistence."""

    @abstractmethod
    def save_tag_translation(self, tag_id: UUID, language: str, name: str) -> None:
        """Save or update a tag translation."""
        ...

    @abstractmethod
    def find_tags_without_translation(
        self, language: str, limit: int
    ) -> List[dict]:
        """Find tags that don't have translation for the target language."""
        ...

    @abstractmethod
    def save_group_translation(
        self, tag_group_definition_id: UUID, language: str, display_name: str, description: str | None = None
    ) -> None:
        """Save or update a tag group display_name and description translation."""
        ...

    @abstractmethod
    def find_groups_without_translation(
        self, language: str, limit: int
    ) -> List[dict]:
        """Find tag group definitions without translation for the target language."""
        ...
