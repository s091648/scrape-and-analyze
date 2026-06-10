from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class TagNormalizationCompletedEvent:
    """Published by TagNormalizationHandler after successful tag normalization."""
    analysis_id: UUID
    article_id: UUID
    article_title: str = ""
    article_content: str = ""
    topic_id: Optional[UUID] = None
