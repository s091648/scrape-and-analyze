from .quota_strategy import QuotaStrategy


class NoOpStrategy(QuotaStrategy):
    """Quota strategy that performs no rate limiting; all calls pass through immediately."""
    def acquire(self, estimated_tokens: int) -> None:
        ...

    def record_usage(self, actual_tokens: int) -> None:
        ...

    def update_batch_size(self, batch_size: int) -> None:
        ...