import pytest


def test_request_strategy_is_abstract():
    from src.analyzers.request_strategy import RequestStrategy
    with pytest.raises(TypeError):
        RequestStrategy()


def test_request_strategy_requires_acquire():
    from src.analyzers.request_strategy import RequestStrategy

    class MissingAcquire(RequestStrategy):
        def record_usage(self, actual_tokens: int) -> None:
            pass

    with pytest.raises(TypeError):
        MissingAcquire()


def test_request_strategy_requires_record_usage():
    from src.analyzers.request_strategy import RequestStrategy

    class MissingRecord(RequestStrategy):
        def acquire(self, estimated_tokens: int) -> None:
            pass

    with pytest.raises(TypeError):
        MissingRecord()


def test_rate_limit_exhausted_is_exception():
    from src.analyzers.request_strategy import RateLimitExhausted
    exc = RateLimitExhausted("daily limit hit")
    assert isinstance(exc, Exception)
    assert str(exc) == "daily limit hit"


def test_noop_strategy_acquire_does_nothing():
    from src.analyzers.request_strategy import NoOpStrategy
    s = NoOpStrategy()
    s.acquire(1000)  # must not raise or sleep


def test_noop_strategy_record_usage_does_nothing():
    from src.analyzers.request_strategy import NoOpStrategy
    s = NoOpStrategy()
    s.record_usage(500)  # must not raise
