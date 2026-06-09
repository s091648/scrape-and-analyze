from dataclasses import dataclass
from typing import Optional, List
from .analysis_tag_group import AnalysisTagGroup


@dataclass
class AnalysisContent:
    """Value object holding extracted analysis fields: summary, pain points, insights, innovations, and tag groups."""
    pain_points: Optional[str]
    insights: Optional[str]
    innovations: Optional[str]
    summary: Optional[str]
    tag_groups: Optional[List[AnalysisTagGroup]]
