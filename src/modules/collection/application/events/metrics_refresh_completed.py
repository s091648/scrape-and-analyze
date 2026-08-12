from dataclasses import dataclass, field
from typing import Tuple

from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta


@dataclass(frozen=True)
class MetricsRefreshCompletedEvent:
    """Event published when the refresh_metrics scheduled job finishes."""
    total: int
    refreshed: int
    failed: int
    execution: JobExecutionMeta
    # provider_names that hit a real rate limit this run (ResilientMetricsService.
    # exhausted_providers) — without this, a run where every article got skipped
    # because a provider is rate-limited looks identical to "nothing needed
    # updating" (both show refreshed=0, failed=0).
    rate_limited_providers: Tuple[str, ...] = field(default_factory=tuple)
