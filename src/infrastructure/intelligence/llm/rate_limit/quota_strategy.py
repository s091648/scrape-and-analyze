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

    @abstractmethod
    def try_acquire(self, estimated_tokens: int) -> bool:
        """Non-blocking reservation attempt: if a slot is immediately
        available, reserve it (same effect as `acquire()`) and return True;
        otherwise reserve nothing and return False. Lets async callers do the
        common "capacity is free" case synchronously on the event loop
        thread, without an `asyncio.to_thread` hop — closing the race where
        that hop's reservation lands after a concurrently-gathered task's
        `has_capacity()` peek already ran (both then pick the same handler).
        Falling back to `acquire()` is still required when this returns
        False."""
        ...