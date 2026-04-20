from abc import ABC, abstractmethod


class RequestStrategy(ABC):
    @abstractmethod
    def acquire(self, estimated_tokens: int) -> None:
        """Block until a request slot is available."""
        ...

    @abstractmethod
    def record_usage(self, actual_tokens: int) -> None:
        """Update sliding windows after a successful call."""
        ...
