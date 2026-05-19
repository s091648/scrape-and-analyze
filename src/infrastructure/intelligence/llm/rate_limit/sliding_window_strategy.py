import threading
import time
from collections import deque
from typing import Deque, Tuple

from .quota_strategy import QuotaStrategy


class RateLimitExhausted(Exception):
    """Raised when a provider's daily request cap is reached."""


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
        while True:
            wait = self._compute_wait(estimated_tokens)
            if wait == 0:
                return
            time.sleep(wait)

    def record_usage(self, actual_tokens: int) -> None:
        with self._lock:
            now = time.monotonic()
            if self._tpm_window:
                self._tpm_window.pop()
            self._tpm_window.append((now, actual_tokens))

    def update_batch_size(self, batch_size: int) -> None:
        with self._lock:
            self.batch_size = batch_size

    def _compute_wait(self, estimated_tokens: int) -> float:
        with self._lock:
            if self._daily_count >= self.rpd:
                raise RateLimitExhausted(f"Daily request limit of {self.rpd} reached")
            now = time.monotonic()
            self._evict_stale(now)
            wait = max(self._rpm_wait(now), self._tpm_wait(now, estimated_tokens))
            if wait == 0:
                self._rpm_window.extend([now] * self.batch_size)
                self._daily_count += 1
                self._tpm_window.append((now, estimated_tokens))
            return wait

    def _evict_stale(self, now: float) -> None:
        cutoff = now - self._WINDOW
        while self._rpm_window and self._rpm_window[0] < cutoff:
            self._rpm_window.popleft()
        while self._tpm_window and self._tpm_window[0][0] < cutoff:
            self._tpm_window.popleft()

    def _rpm_wait(self, now: float) -> float:
        if len(self._rpm_window) < self.rpm:
            return 0.0
        return self._WINDOW - (now - self._rpm_window[0])

    def _tpm_wait(self, now: float, estimated_tokens: int) -> float:
        used = sum(t for _, t in self._tpm_window)
        if used + estimated_tokens <= self.tpm:
            return 0.0
        return self._WINDOW - (now - self._tpm_window[0][0])
