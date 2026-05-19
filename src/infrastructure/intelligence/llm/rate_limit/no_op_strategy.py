from .quota_strategy import QuotaStrategy


class NoOpStrategy(QuotaStrategy):
    def acquire(self, estimated_tokens: int) -> None:
        ...

    def record_usage(self, actual_tokens: int) -> None:
        ...

    def update_batch_size(self, batch_size: int) -> None:
        ...