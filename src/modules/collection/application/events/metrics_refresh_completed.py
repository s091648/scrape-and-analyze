from dataclasses import dataclass


@dataclass(frozen=True)
class MetricsRefreshCompletedEvent:
    """Event published when the refresh_metrics scheduled job finishes."""
    total: int
    refreshed: int
    failed: int
    duration_seconds: float
