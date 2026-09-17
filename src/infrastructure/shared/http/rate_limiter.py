"""
Per-domain token-bucket rate limiter.

Each domain gets its own bucket refilling at a configurable RPM.
`acquire()` blocks until a token is available.

Domains listed in _SINGLE_CONNECTION_DOMAINS additionally enforce
"at most one concurrent open connection" via a per-domain semaphore,
matching the arXiv API TOS requirement.

Default limits (RPM):
  - export.arxiv.org + arxiv.org → 15 combined (arXiv API TOS: ≤ 1 req/3s ≈ 20 RPM,
    single connection, applies per IP across every host under our control — a
    separate 15 RPM bucket per host would let the two combine to 30 RPM against
    that same shared budget, so both hosts share one bucket and one connection
    semaphore; see _SHARED_BUCKET_GROUPS)
  - everything else   → 15
"""
import time
import threading
from contextlib import contextmanager
from typing import Callable, Optional

_DEFAULT_RPM: float = 15.0

# How often a blocked acquire() re-checks whether its domain's circuit tripped
# while it waits for the next token. Without this, a caller that entered the
# wait *before* another thread tripped the circuit would still ride out the
# full refill interval (up to 60s for a 1 RPM domain) and then send a real,
# doomed request anyway — see DomainRateLimiter.acquire()'s docstring.
_TRIP_POLL_INTERVAL_SECONDS = 1.0

# Hardcoded conservative defaults; can be overridden via env or constructor.
# Sites marked with ⚠ have known anti-bot protections — keep RPM very low.
_BUILTIN_OVERRIDES: dict[str, float] = {
    "arxiv.org": 15.0,  # arXiv TOS: ≤1 req/3s ≈ 20 RPM, one shared budget across
                         # export.arxiv.org + arxiv.org — see _SHARED_BUCKET_GROUPS
    "www.iotworldtoday.com": 2.0,   # ⚠ anti-bot (Cloudflare)
    "iotworldtoday.com": 2.0,
    "api.semanticscholar.org": 1.0,  # unauthenticated: ~100 req/day; scraper max 50-min run → ≤50 req/day
    "api.openalex.org": 450.0,        # official: 10 req/sec (600 RPM) + 100k/day; leaves headroom under the daily cap
}

# Domains that draw from the same arXiv TOS budget (same IP allowance) and must
# therefore share one token bucket + one "single connection at a time"
# semaphore, keyed under the mapped canonical domain — otherwise each domain's
# own 15 RPM bucket would let the pair combine to 30 RPM / 2 concurrent
# connections against that one shared budget (CodeRabbit review,
# 026-rate-limit-codegen PR #127).
_SHARED_BUCKET_GROUPS: dict[str, str] = {
    "export.arxiv.org": "arxiv.org",
    "arxiv.org": "arxiv.org",
}

# Domains that must also enforce "single connection at a time" (arXiv TOS) —
# checked against the resolved bucket-group key, so export.arxiv.org and
# arxiv.org share the same semaphore instance.
_SINGLE_CONNECTION_DOMAINS: frozenset[str] = frozenset({
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
        """Return the token bucket for domain (or its shared bucket-group key, for
        domains that must draw from the same budget — see _SHARED_BUCKET_GROUPS),
        creating one with the configured RPM if new."""
        key = _SHARED_BUCKET_GROUPS.get(domain, domain)
        with self._lock:
            if key not in self._buckets:
                rpm = self._rpm_map.get(domain, self._rpm_map.get(key, _DEFAULT_RPM))
                self._buckets[key] = _TokenBucket(rpm)
            return self._buckets[key]

    def _get_semaphore(self, domain: str) -> threading.Semaphore:
        """Return the concurrency semaphore for domain (or its shared bucket-group
        key), single-slot for arXiv TOS domains."""
        key = _SHARED_BUCKET_GROUPS.get(domain, domain)
        with self._lock:
            if key not in self._semaphores:
                limit = 1 if key in _SINGLE_CONNECTION_DOMAINS else 10
                self._semaphores[key] = threading.Semaphore(limit)
            return self._semaphores[key]
