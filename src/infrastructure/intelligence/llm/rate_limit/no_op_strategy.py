from src.infrastructure.intelligence.llm.rate_limit.request_strategy import RequestStrategy


class NoOpStrategy(RequestStrategy):
    def acquire(self, estimated_tokens: int) -> None:
        pass

    def record_usage(self, actual_tokens: int) -> None:
        pass
