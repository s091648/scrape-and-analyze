from dataclasses import dataclass
from typing import Optional
from src.modules.intelligence.domain.value_objects import TagGroup


@dataclass
class AnalysisContent:
    pain_points: Optional[str]
    insights: Optional[str]
    innovations: Optional[str]
    summary: Optional[str]
    tag_groups: Optional[list[TagGroup]]