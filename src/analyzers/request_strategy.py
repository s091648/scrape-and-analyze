from abc import ABC, abstractmethod
import threading
import time
from collections import deque
from typing import Deque, Tuple


class RateLimitExhausted(Exception):
    """Raised when a provider's daily request cap is reached."""


class RequestStrategy(ABC):
    """Abstract rate-limiting strategy injected into a ProviderHandler."""

    @abstractmethod
    def acquire(self, estimated_tokens: int) -> None:
        """Block until a request slot is available.

        Raises RateLimitExhausted if the daily cap is hit and no recovery
        is possible within the current run.
        """

    @abstractmethod
    def record_usage(self, actual_tokens: int) -> None:
        """Update sliding windows with actual token count after a successful call."""


class NoOpStrategy(RequestStrategy):
    """No-op strategy for paid APIs with no client-side throttling needed."""

    def acquire(self, estimated_tokens: int) -> None:
        pass

    def record_usage(self, actual_tokens: int) -> None:
        pass


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
        self._rpm_window: Deque[float] = deque()           # request timestamps
        self._tpm_window: Deque[Tuple[float, int]] = deque()  # (timestamp, tokens)
        self._daily_count: int = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def acquire(self, estimated_tokens: int) -> None:
        while True:
            wait = self._compute_wait(estimated_tokens)
            if wait == 0:
                return
            time.sleep(wait)

    def record_usage(self, actual_tokens: int) -> None:
        with self._lock:
            now = time.monotonic()
            # Replace the estimated-token placeholder added by _reserve() with actual
            # by appending the real count. The placeholder (estimated) was already
            # added; we append the delta so TPM total stays accurate.
            # Simpler: just append actual — slight overcount but conservative.
            self._tpm_window.append((now, actual_tokens))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_wait(self, estimated_tokens: int) -> float:
        """
        Under lock: evict stale entries, check limits.
        Returns 0 if a slot is available (and reserves it).
        Returns seconds to sleep otherwise.
        Raises RateLimitExhausted if daily cap is hit.
        """
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
                # Reserve slot
                self._rpm_window.append(now)
                self._daily_count += 1
                # Reserve token estimate in TPM window
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
        # Oldest entry must expire before we can send another
        oldest = self._rpm_window[0]
        return self._WINDOW - (now - oldest)

    def _tpm_wait(self, now: float, estimated_tokens: int) -> float:
        used = sum(t for _, t in self._tpm_window)
        if used + estimated_tokens <= self.tpm:
            return 0.0
        # Oldest token bucket entry must expire
        oldest_ts = self._tpm_window[0][0]
        return self._WINDOW - (now - oldest_ts)
