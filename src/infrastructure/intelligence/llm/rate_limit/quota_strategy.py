from abc import ABC, abstractmethod


class QuotaStrategy(ABC):
    """Abstract base for LLM API quota/rate-limit strategies."""
    @abstractmethod
    def acquire(self, estimated_tokens: int) -> None:
        """Block until a request slot is available."""
        ...

    @abstractmethod
    def record_usage(self, actual_tokens: int) -> None:
        """Update sliding windows after a successful call."""
        ...

    @abstractmethod
    def update_batch_size(self, batch_size: int) -> None:
        """Inform the strategy of the current batch size for better estimation."""
        ...