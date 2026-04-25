from dataclasses import dataclass
from typing import List

from src.modules.collection.application.use_cases import SourceStats


@dataclass(frozen=True)
class PipelineCompletedEvent:
    stats: List[SourceStats]
    duration_seconds: float