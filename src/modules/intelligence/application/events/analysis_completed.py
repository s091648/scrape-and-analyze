from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AnalysisCompletedEvent:
    """Published by AnalyzeArticleUseCase after successful analysis save."""
    analysis_id: UUID
    article_id: UUID
