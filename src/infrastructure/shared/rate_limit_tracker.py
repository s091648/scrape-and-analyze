import threading
from typing import List


class RateLimitedProviderTracker:
    """Thread-safe, run-scoped memory of identifiers (provider names, hostnames,
    ...) that have already hit a rate limit once this run.

    Each owner (ResilientLLMService, ResilientEmbeddingService,
    ResilientMetricsService, ScrapeExecutor, ...) holds its own instance — the
    state is per-run and per-subsystem, deliberately NOT shared across
    services, since each subsystem tracks a different kind of identifier
    (HTTP hostname for ScrapeExecutor, provider_name for the LLM/metrics
    resilient services) with no common ID space to unify them into. What's
    shared is this small primitive, not the state itself.
    """

    def __init__(self) -> None:
        self._exhausted: set[str] = set()
        self._lock = threading.Lock()

    def mark_exhausted(self, identifier: str) -> None:
        """Record that `identifier` hit a rate limit — idempotent."""
        with self._lock:
            self._exhausted.add(identifier)

    def is_exhausted(self, identifier: str) -> bool:
        with self._lock:
            return identifier in self._exhausted

    @property
    def exhausted(self) -> List[str]:
        """Sorted snapshot of every identifier marked exhausted so far this run."""
        with self._lock:
            return sorted(self._exhausted)
