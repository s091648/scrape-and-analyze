import pytest


def test_quota_strategy_is_abstract():
    from src.infrastructure.intelligence.llm.rate_limit.quota_strategy import QuotaStrategy
    with pytest.raises(TypeError):
        QuotaStrategy()


def test_quota_strategy_requires_acquire():
    from src.infrastructure.intelligence.llm.rate_limit.quota_strategy import QuotaStrategy

    class MissingAcquire(QuotaStrategy):
        pass

    with pytest.raises(TypeError):
        MissingAcquire()


def test_no_op_strategy_does_not_raise():
    from src.infrastructure.intelligence.llm.rate_limit.no_op_strategy import NoOpStrategy
    strategy = NoOpStrategy()
    strategy.acquire(estimated_tokens=1000)
    strategy.record_usage(actual_tokens=500)