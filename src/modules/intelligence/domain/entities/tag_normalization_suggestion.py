from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.modules.intelligence.domain.exceptions import (
    InvalidSimilarityScoreError,
    InvalidSuggestionStatusError,
)

_VALID_STATUSES = frozenset({"pending", "approved", "rejected"})


@dataclass
class TagNormalizationSuggestion:
    """Tracks a suggestion to merge a new tag into an existing similar tag."""
    new_tag_id: UUID
    existing_tag_id: UUID
    similarity_score: float
    article_id: UUID
    status: str = "pending"           # pending | approved | rejected
    id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[UUID] = None

    def __post_init__(self) -> None:
        if self.status not in _VALID_STATUSES:
            raise InvalidSuggestionStatusError(
                f"status must be one of {sorted(_VALID_STATUSES)}, got: {self.status!r}"
            )
        if not 0.0 <= self.similarity_score <= 1.0:
            raise InvalidSimilarityScoreError(
                f"similarity_score must be within [0.0, 1.0], got: {self.similarity_score!r}"
            )
