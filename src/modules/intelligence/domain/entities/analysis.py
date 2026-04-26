from typing import Optional
from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime
from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata


@dataclass
class Analysis:
    article_id: UUID
    analysis_content: AnalysisContent
    analysis_metadata: AnalysisMetadata
    id: UUID = field(default_factory=uuid4)
    analyzed_at: Optional[datetime] = None
