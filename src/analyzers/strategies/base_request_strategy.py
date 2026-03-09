from abc import ABC, abstractmethod


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
