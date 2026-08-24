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

    @abstractmethod
    def has_capacity(self, estimated_tokens: int = 0) -> bool:
        """Non-blocking, side-effect-free check: True if a request could be
        dispatched right now without waiting (024-async-pipeline-refactor,
        ProviderSelector port — see contracts/provider-selector-port.md).
        Never reserves capacity; only `acquire()` does that."""
        ...