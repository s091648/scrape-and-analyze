import threading
import time
from collections import deque
from typing import Deque, Tuple

from .quota_strategy import QuotaStrategy


class RateLimitExhausted(Exception):
    """Raised when a provider's daily request cap is reached and no more calls should be made."""


class SlidingWindowStrategy(QuotaStrategy):
    """
    Sliding-window rate limiter for LLM API quota management.

    Tracks requests and token usage within a rolling 60-second window,
    blocking until capacity is available. Also enforces a hard daily cap (rpd).

    Args:
        rpm: Max requests per minute.
        tpm: Max tokens per minute.
        rpd: Max requests per day (raises RateLimitExhausted when reached).
    """

    _WINDOW = 60.0

    def __init__(self, rpm: int, tpm: int, rpd: int, batch_size: int = 1) -> None:
        self.rpm = rpm
        self.tpm = tpm
        self.rpd = rpd
        self.batch_size = batch_size    
        self._rpm_window: Deque[float] = deque()
        self._tpm_window: Deque[Tuple[float, int]] = deque()
        self._daily_count: int = 0
        self._lock = threading.Lock()

    def acquire(self, estimated_tokens: int) -> None:
        """Block until a request slot and token budget are available within RPM/TPM/RPD limits."""
        while True:
            wait = self._compute_wait(estimated_tokens)
            if wait == 0:
                return
            time.sleep(wait)

    def try_acquire(self, estimated_tokens: int) -> bool:
        """Non-blocking: reserve a slot only if immediately available.
        `_compute_wait()` already only reserves when it returns 0, so this
        is just that check without ever sleeping."""
        return self._compute_wait(estimated_tokens) == 0

    def record_usage(self, actual_tokens: int) -> None:
        """Record actual token usage in the sliding window after a successful API call."""
        with self._lock:
            now = time.monotonic()
            if self._tpm_window:
                self._tpm_window.pop()
            self._tpm_window.append((now, actual_tokens))

    def update_batch_size(self, batch_size: int) -> None:
        """Update the batch size used for RPM pre-accounting when acquire is called."""
        with self._lock:
            self.batch_size = batch_size

    def has_capacity(self, estimated_tokens: int = 0) -> bool:
        """024-async-pipeline-refactor: non-blocking peek for ProviderSelector
        (contracts/provider-selector-port.md) — True if `acquire()` would
        return immediately right now, without ever calling `time.sleep()`.
        Reuses the same RPM/TPM/RPD internals as `_compute_wait()` but never
        reserves a slot (no window insert, no `_daily_count` increment) —
        eviction of stale entries is harmless housekeeping, not a reservation."""
        with self._lock:
            if self._daily_count >= self.rpd:
                return False
            now = time.monotonic()
            self._evict_stale(now)
            return self._rpm_wait(now) == 0 and self._tpm_wait(now, estimated_tokens) == 0

    def _compute_wait(self, estimated_tokens: int) -> float:
        """Calculate wait time for capacity, or record the request if capacity exists."""
        with self._lock:
            if self._daily_count >= self.rpd:
                raise RateLimitExhausted(f"Daily request limit of {self.rpd} reached")
            now = time.monotonic()
            self._evict_stale(now)
            wait = max(self._rpm_wait(now), self._tpm_wait(now, estimated_tokens))
            if wait == 0:
                self._rpm_window.extend([now] * self.batch_size)
                self._daily_count += self.batch_size
                self._tpm_window.append((now, estimated_tokens))
            return wait

    def _evict_stale(self, now: float) -> None:
        """Remove entries older than the sliding window from both rpm and tpm deques."""
        cutoff = now - self._WINDOW
        while self._rpm_window and self._rpm_window[0] < cutoff:
            self._rpm_window.popleft()
        while self._tpm_window and self._tpm_window[0][0] < cutoff:
            self._tpm_window.popleft()

    def _rpm_wait(self, now: float) -> float:
        """Return seconds until an RPM slot frees up, or 0 if capacity is available."""
        if len(self._rpm_window) + self.batch_size <= self.rpm:
            return 0.0
        if not self._rpm_window:
            return 0.0
        return self._WINDOW - (now - self._rpm_window[0])

    def _tpm_wait(self, now: float, estimated_tokens: int) -> float:
        """Return seconds until TPM capacity frees up, or 0 if tokens fit in the window."""
        used = sum(t for _, t in self._tpm_window)
        if used + estimated_tokens <= self.tpm:
            return 0.0
        return self._WINDOW - (now - self._tpm_window[0][0])
