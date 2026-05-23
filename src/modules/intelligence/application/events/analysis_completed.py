from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class AnalysisCompletedEvent:
    """Published by ArticleProcessedHandler after successful analysis save."""
    analysis_id: UUID
    article_id: UUID
    tag_groups: tuple = field(default_factory=tuple)
    # tuple of (group_name: str, tags: list[str]) — passed through to TagNormalizationHandler
