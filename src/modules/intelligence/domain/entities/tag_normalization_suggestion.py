from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


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
