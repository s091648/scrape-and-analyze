from dataclasses import dataclass
from typing import Optional
from .tag_group import TagGroup


@dataclass
class AnalysisContent:
    pain_points: Optional[str]
    insights: Optional[str]
    innovations: Optional[str]
    summary: Optional[str]
    tag_groups: Optional[list[TagGroup]]