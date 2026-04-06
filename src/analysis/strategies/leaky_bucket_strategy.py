import threading
import time
from collections import deque
from typing import Deque, Tuple
from src.analysis.strategies.base_request_strategy import RequestStrategy


class RateLimitExhausted(Exception):
    """Raised when a provider's daily request cap is reached."""


class LeakyBucketStrategy(RequestStrategy):
    """
    Sliding-window rate limiter enforcing RPM, TPM, and daily request cap.

    Thread-safe: uses a lock to read/compute wait time, releases before sleeping,
    then retries — so other threads are never blocked during a sleep.
    """

    _WINDOW = 60.0  # seconds

    def __init__(self, rpm: int, tpm: int, rpd: int) -> None:
        self.rpm = rpm
        self.tpm = tpm
        self.rpd = rpd
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

    def _compute_wait(self, estimated_tokens: int) -> float:
        with self._lock:
            if self._daily_count >= self.rpd:
                raise RateLimitExhausted(
                    f"Daily request limit of {self.rpd} reached"
                )
            now = time.monotonic()
            self._evict_stale(now)
            rpm_wait = self._rpm_wait(now)
            tpm_wait = self._tpm_wait(now, estimated_tokens)
            wait = max(rpm_wait, tpm_wait)
            if wait == 0:
                self._rpm_window.append(now)
                self._daily_count += 1
                self._tpm_window.append((now, estimated_tokens))
                return 0
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
        oldest = self._rpm_window[0]
        return self._WINDOW - (now - oldest)

    def _tpm_wait(self, now: float, estimated_tokens: int) -> float:
        used = sum(t for _, t in self._tpm_window)
        if used + estimated_tokens <= self.tpm:
            return 0.0
        oldest_ts = self._tpm_window[0][0]
        return self._WINDOW - (now - oldest_ts)
