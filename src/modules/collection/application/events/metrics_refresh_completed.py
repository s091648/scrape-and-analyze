from dataclasses import dataclass

from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta


@dataclass(frozen=True)
class MetricsRefreshCompletedEvent:
    """Event published when the refresh_metrics scheduled job finishes."""
    total: int
    refreshed: int
    failed: int
    execution: JobExecutionMeta
