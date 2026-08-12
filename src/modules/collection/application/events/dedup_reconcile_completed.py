from dataclasses import dataclass

from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta


@dataclass(frozen=True)
class DedupReconcileCompletedEvent:
    """Event published when the dedup_reconcile scheduled job finishes."""
    total: int
    healed: int
    merged: int
    failed: int
    execution: JobExecutionMeta
