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
from typing import Callable, Optional

_DEFAULT_RPM: float = 10.0

# How often a blocked acquire() re-checks whether its domain's circuit tripped
# while it waits for the next token. Without this, a caller that entered the
# wait *before* another thread tripped the circuit would still ride out the
# full refill interval (up to 60s for a 1 RPM domain) and then send a real,
# doomed request anyway — see DomainRateLimiter.acquire()'s docstring.
_TRIP_POLL_INTERVAL_SECONDS = 1.0

# Hardcoded conservative defaults; can be overridden via env or constructor.
# Sites marked with ⚠ have known anti-bot protections — keep RPM very low.
_BUILTIN_OVERRIDES: dict[str, float] = {
    "export.arxiv.org": 3.0,
    "arxiv.org": 3.0,   # arXiv TOS: same budget as API domain (shared IP)
    "www.iotworldtoday.com": 2.0,   # ⚠ anti-bot (Cloudflare)
    "iotworldtoday.com": 2.0,
    "api.semanticscholar.org": 1.0,  # unauthenticated: ~100 req/day; scraper max 50-min run → ≤50 req/day
    "api.openalex.org": 5.0,          # polite pool: 10 req/sec; conservative default
}

# Domains that must also enforce "single connection at a time" (arXiv TOS).
_SINGLE_CONNECTION_DOMAINS: frozenset[str] = frozenset({
    "export.arxiv.org",
    "arxiv.org",
})


class DomainCircuitOpenError(Exception):
    """Raised when a domain already returned 429 earlier in this run. External
    APIs' 429s (daily/pool quota exhaustion) don't clear within a single run,
    so further requests are short-circuited locally instead of pacing out more
    doomed calls — callers should treat this the same as a fresh 429."""


class _TokenBucket:
    """Single-domain token bucket. NOT thread-safe on its own; lock is held by caller."""

    def __init__(self, rpm: float) -> None:
        self._capacity: float = rpm
        self._tokens: float = 1.0         # start with 1 token (avoid burst at startup)
        self._refill_rate: float = rpm / 60.0  # tokens per second
        self._last_refill: float = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, is_tripped: Optional[Callable[[], bool]] = None) -> None:
        """Block until one token is available, then consume it.

        If `is_tripped` is given, it's polled every _TRIP_POLL_INTERVAL_SECONDS
        while waiting so a circuit trip that happens mid-wait (another thread's
        call just failed) is noticed within a second or two instead of only
        after the full refill interval elapses. Returns early — without
        consuming a token — the moment `is_tripped()` reports True; the caller
        is responsible for re-checking and raising.
        """
        while True:
            if is_tripped is not None and is_tripped():
                return
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
            if is_tripped is not None:
                wait = min(wait, _TRIP_POLL_INTERVAL_SECONDS)
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
        self._tripped_domains: set[str] = set()
        self._lock = threading.Lock()

    def note_rate_limited(self, domain: str) -> None:
        """Trip the circuit for *domain*: further acquire()/connection() calls
        raise DomainCircuitOpenError immediately for the rest of this process,
        instead of waiting out the token bucket to send another request that's
        very likely to also 429."""
        with self._lock:
            self._tripped_domains.add(domain)

    def acquire(self, domain: str) -> None:
        """Block until a request token is available for *domain*.

        Raises DomainCircuitOpenError immediately (no wait, no request) if a
        prior call to this domain already recorded a 429 via note_rate_limited().

        Also re-checked after the token-bucket wait, not just before it: with
        several concurrent callers racing in before any of them has failed yet
        (e.g. refresh_metrics.py's --concurrency workers all starting at once),
        one gets the only available token and trips the circuit on failure —
        but the others are already past this method's entry check and blocked
        inside the bucket's wait for the *next* token (up to 60s on a 1 RPM
        domain). Without a second check here, each of those stragglers would
        still wake up, ignore the now-tripped circuit, and send its own real,
        doomed request. _TokenBucket.acquire() also polls is_tripped while it
        waits, so a straggler bails within ~1s of the trip rather than riding
        out the full refill interval.
        """
        self._raise_if_tripped(domain)
        bucket = self._get_or_create(domain)
        bucket.acquire(is_tripped=lambda: self._is_tripped(domain))
        self._raise_if_tripped(domain)

    def _is_tripped(self, domain: str) -> bool:
        with self._lock:
            return domain in self._tripped_domains

    def _raise_if_tripped(self, domain: str) -> None:
        if self._is_tripped(domain):
            raise DomainCircuitOpenError(domain)

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
        """Return the token bucket for domain, creating one with the configured RPM if new."""
        with self._lock:
            if domain not in self._buckets:
                rpm = self._rpm_map.get(domain, _DEFAULT_RPM)
                self._buckets[domain] = _TokenBucket(rpm)
            return self._buckets[domain]

    def _get_semaphore(self, domain: str) -> threading.Semaphore:
        """Return the concurrency semaphore for domain, single-slot for arXiv TOS domains."""
        with self._lock:
            if domain not in self._semaphores:
                limit = 1 if domain in _SINGLE_CONNECTION_DOMAINS else 10
                self._semaphores[domain] = threading.Semaphore(limit)
            return self._semaphores[domain]
