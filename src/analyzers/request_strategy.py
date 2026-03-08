from abc import ABC, abstractmethod


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
