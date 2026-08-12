from dataclasses import dataclass

from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta


@dataclass(frozen=True)
class RagBackfillCompletedEvent:
    """Event published when the backfill_rag scheduled job finishes."""
    total: int
    succeeded: int
    failed: int
    execution: JobExecutionMeta
