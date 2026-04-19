from typing import Optional
from dataclasses import dataclass, field
from uuid import UUID
from datetime import datetime
from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata


@dataclass
class Analysis:
    id: UUID = field(default_factory=UUID)
    article_id: UUID
    correlation_id: UUID
    analysis_content: AnalysisContent
    analysis_metadata: AnalysisMetadata
    analyzed_at: Optional[datetime] = None
