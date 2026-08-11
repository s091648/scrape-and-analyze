from dataclasses import dataclass
from typing import List

from src.modules.collection.application.use_cases import SourceStats
from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta


@dataclass(frozen=True)
class PipelineCompletedEvent:
    """Event published when the full scrape pipeline finishes, carrying per-source stats and execution metadata."""
    stats: List[SourceStats]
    execution: JobExecutionMeta
