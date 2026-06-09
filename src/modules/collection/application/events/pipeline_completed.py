from dataclasses import dataclass
from typing import List

from src.modules.collection.application.use_cases import SourceStats


@dataclass(frozen=True)
class PipelineCompletedEvent:
    """Event published when the full scrape pipeline finishes, carrying per-source stats and total duration."""
    stats: List[SourceStats]
    duration_seconds: float