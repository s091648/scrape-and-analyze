"""
Per-domain token-bucket rate limiter.

Each domain gets its own bucket refilling at a configurable RPM.
`acquire()` blocks until a token is available.

Domains listed in _SINGLE_CONNECTION_DOMAINS additionally enforce
"at most one concurrent open connection" via a per-domain semaphore,
matching the arXiv API TOS requirement.

Default limits (RPM):
  - export.arxiv.org  → 3   (arXiv API TOS: ≤ 1 req/3s, single connection)
  - arxiv.org         → 3   (PDF downloads — same TOS, same IP budget)
  - everything else   → 10
"""
import time
import threading
from contextlib import contextmanager

_DEFAULT_RPM: float = 10.0

# Hardcoded conservative defaults; can be overridden via env or constructor.
# Sites marked with ⚠ have known anti-bot protections — keep RPM very low.
_BUILTIN_OVERRIDES: dict[str, float] = {
    "export.arxiv.org": 3.0,
    "arxiv.org": 3.0,   # arXiv TOS: same budget as API domain (shared IP)
    "www.iotworldtoday.com": 2.0,   # ⚠ anti-bot (Cloudflare)
    "iotworldtoday.com": 2.0,
    "api.semanticscholar.org": 1.0,  # unauthenticated: ~100 req/day; keep well under limit
    "api.openalex.org": 5.0,          # polite pool: 10 req/sec; conservative default
}

# Domains that must also enforce "single connection at a time" (arXiv TOS).
_SINGLE_CONNECTION_DOMAINS: frozenset[str] = frozenset({
    "export.arxiv.org",
    "arxiv.org",
})


class _TokenBucket:
    """Single-domain token bucket. NOT thread-safe on its own; lock is held by caller."""

    def __init__(self, rpm: float) -> None:
        self._capacity: float = rpm
        self._tokens: float = 1.0         # start with 1 token (avoid burst at startup)
        self._refill_rate: float = rpm / 60.0  # tokens per second
        self._last_refill: float = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until one token is available, then consume it."""
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(
                    self._capacity,
                    self._tokens + elapsed * self._refill_rate,
                )
                self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                # How long until the next token arrives
                wait = (1.0 - self._tokens) / self._refill_rate
            time.sleep(wait)


class DomainRateLimiter:
    """
    Thread-safe per-domain rate limiter.

    For domains in _SINGLE_CONNECTION_DOMAINS (e.g. arXiv), also enforces
    "at most one concurrent open connection" via a semaphore, satisfying the
    arXiv API TOS requirement.

    Args:
        overrides: Additional ``{domain: rpm}`` mappings that take precedence
                   over the built-in defaults.
    """

    def __init__(self, overrides: dict[str, float] | None = None) -> None:
        self._rpm_map: dict[str, float] = {**_BUILTIN_OVERRIDES, **(overrides or {})}
        self._buckets: dict[str, _TokenBucket] = {}
        self._semaphores: dict[str, threading.Semaphore] = {}
        self._lock = threading.Lock()

    def acquire(self, domain: str) -> None:
        """Block until a request token is available for *domain*."""
        bucket = self._get_or_create(domain)
        bucket.acquire()

    @contextmanager
    def connection(self, domain: str):
        """
        Context manager that rate-limits AND, for single-connection domains,
        holds the concurrency semaphore for the duration of the request.

        Usage::

            with rate_limiter.connection(domain):
                response = requests.get(url, ...)
        """
        self.acquire(domain)
        sem = self._get_semaphore(domain)
        sem.acquire()
        try:
            yield
        finally:
            sem.release()

    # ── internal ──────────────────────────────────────────────────────────

    def _get_or_create(self, domain: str) -> _TokenBucket:
        with self._lock:
            if domain not in self._buckets:
                rpm = self._rpm_map.get(domain, _DEFAULT_RPM)
                self._buckets[domain] = _TokenBucket(rpm)
            return self._buckets[domain]

    def _get_semaphore(self, domain: str) -> threading.Semaphore:
        with self._lock:
            if domain not in self._semaphores:
                limit = 1 if domain in _SINGLE_CONNECTION_DOMAINS else 10
                self._semaphores[domain] = threading.Semaphore(limit)
            return self._semaphores[domain]
