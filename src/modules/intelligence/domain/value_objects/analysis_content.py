from dataclasses import dataclass
from typing import Optional, List
from .analysis_tag_group import AnalysisTagGroup


@dataclass
class AnalysisContent:
    pain_points: Optional[str]
    insights: Optional[str]
    innovations: Optional[str]
    summary: Optional[str]
    tag_groups: Optional[List[AnalysisTagGroup]]
