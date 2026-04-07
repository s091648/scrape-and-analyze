"""
Per-domain token-bucket rate limiter.

Each domain gets its own bucket refilling at a configurable RPM.
`acquire()` blocks until a token is available.

Default limits (RPM):
  - export.arxiv.org  → 3   (arXiv API TOS)
  - arxiv.org         → 5
  - everything else   → 10
"""
import os
import time
import threading
from urllib.parse import urlparse

_DEFAULT_RPM: float = 10.0

# Hardcoded conservative defaults; can be overridden via env or constructor.
# Sites marked with ⚠ have known anti-bot protections — keep RPM very low.
_BUILTIN_OVERRIDES: dict[str, float] = {
    "export.arxiv.org": 3.0,
    "arxiv.org": 5.0,
    "www.iotworldtoday.com": 2.0,   # ⚠ anti-bot (Cloudflare)
    "iotworldtoday.com": 2.0,
}


class _TokenBucket:
    """Single-domain token bucket. NOT thread-safe on its own; lock is held by caller."""

    def __init__(self, rpm: float) -> None:
        self._capacity: float = rpm
        self._tokens: float = rpm          # start full
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

    Args:
        overrides: Additional ``{domain: rpm}`` mappings that take precedence
                   over the built-in defaults.
    """

    def __init__(self, overrides: dict[str, float] | None = None) -> None:
        self._rpm_map: dict[str, float] = {**_BUILTIN_OVERRIDES, **(overrides or {})}
        self._buckets: dict[str, _TokenBucket] = {}
        self._lock = threading.Lock()

    def acquire(self, domain: str) -> None:
        """Block until a request token is available for *domain*."""
        bucket = self._get_or_create(domain)
        bucket.acquire()

    def acquire_for_url(self, url: str) -> None:
        """Convenience: extract domain from *url* then call acquire()."""
        domain = urlparse(url).netloc
        self.acquire(domain)

    # ── internal ──────────────────────────────────────────────────────────

    def _get_or_create(self, domain: str) -> _TokenBucket:
        with self._lock:
            if domain not in self._buckets:
                rpm = self._rpm_map.get(domain, _DEFAULT_RPM)
                self._buckets[domain] = _TokenBucket(rpm)
            return self._buckets[domain]
