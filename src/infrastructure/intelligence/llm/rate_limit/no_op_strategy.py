from .quota_strategy import QuotaStrategy


class NoOpStrategy(QuotaStrategy):
    """Quota strategy that performs no rate limiting; all calls pass through immediately."""
    def acquire(self, estimated_tokens: int) -> None:
        """No-op: immediately allow the request without rate-limit checks."""
        ...

    def record_usage(self, actual_tokens: int) -> None:
        """No-op: discard token usage recording."""
        ...

    def try_acquire(self, estimated_tokens: int) -> bool:
        """No-op: always immediately available."""
        return True

    def update_batch_size(self, batch_size: int) -> None:
        """No-op: ignore batch size updates."""
        ...

    def has_capacity(self, estimated_tokens: int = 0) -> bool:
        """No-op: always has capacity."""
        return True