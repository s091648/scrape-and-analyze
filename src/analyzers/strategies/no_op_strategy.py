from src.analyzers.strategies.base_request_strategy import RequestStrategy

class NoOpStrategy(RequestStrategy):
    """No-op strategy for paid APIs with no client-side throttling needed."""

    def acquire(self, estimated_tokens: int) -> None:
        pass

    def record_usage(self, actual_tokens: int) -> None:
        pass