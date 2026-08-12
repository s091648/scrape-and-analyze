from dataclasses import dataclass
from typing import Any, Callable, Literal, Protocol

# TTL safety net for missed invalidations (FR-008) — under normal operation, entries
# become unreachable via bump_version() long before they'd expire on their own.
DEFAULT_TTL_SECONDS = 60 * 60 * 24  # 24h, matching the daily refresh cadence


@dataclass(frozen=True)
class CacheResult:
    """Wraps get_or_set()'s value with the outcome that produced it, so callers (e.g. routers
    setting an X-Cache response header) can tell a real cache hit apart from a miss or a
    Redis-unavailable bypass without re-deriving it themselves."""
    value: Any
    status: Literal["HIT", "MISS", "BYPASS"]


class CacheGateway(Protocol):
    """Cache-aside reads + namespace-wide invalidation for read-heavy API endpoints.

    See specs/020-redis-caching-layer/contracts/cache-gateway.md for the full contract.
    """

    def get_or_set(
        self,
        namespace: str,
        params: dict,
        ttl_seconds: int,
        loader: Callable[[], Any],
        lang: str = "en",
    ) -> CacheResult:
        """Return a CacheResult wrapping the value for (namespace, params, lang): status="HIT"
        if present and still valid for the namespace's current version; otherwise calls
        loader(), caches the result under the current version, and returns status="MISS".
        Never raises — if the cache backend is unavailable, calls loader() uncached and
        returns status="BYPASS"."""
        ...

    def bump_version(self, namespace: str) -> int:
        """Invalidate every previously-cached entry in `namespace` at once by
        incrementing its version counter. Returns the new version. Never raises —
        no-ops (logging a warning) if the cache backend is unavailable."""
        ...

    def publish_warmup_signal(self, reason: str = "") -> None:
        """Fire-and-forget PUBLISH telling backend's cache-warmup listener to re-populate
        the default (no-customization) reads for every cached namespace — the event-driven
        replacement for the old HTTP self-call CacheWarmupHandler used (020-redis-caching-layer
        follow-up). `reason` is a free-text label (e.g. "scraper_pipeline") carried into the
        listener's log line for observability only — it never changes what gets warmed.
        Never raises — no-ops (logging a warning) if the cache backend is unavailable, same
        posture as bump_version(). Missing this signal is never a correctness issue: the next
        real visitor still gets a correct (if uncached) response via ordinary cache-aside."""
        ...
