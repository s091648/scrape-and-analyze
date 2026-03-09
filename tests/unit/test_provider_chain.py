import pytest
from unittest.mock import MagicMock, call
from src.analyzers.providers.base_llm_provider import AnalysisResult


def _make_result():
    return AnalysisResult(
        tag_groups=[],
        pain_points='p', insights='i', innovations='n',
        input_tokens=100, output_tokens=50
    )


def test_provider_handler_calls_strategy_acquire():
    from src.analyzers.provider_chain import ProviderHandler
    provider = MagicMock()
    strategy = MagicMock()
    provider.analyze.return_value = _make_result()

    handler = ProviderHandler(provider=provider, strategy=strategy, priority=1, name='test')
    handler.analyze('content', 'prompt')

    strategy.acquire.assert_called_once()
    # estimated_tokens should be roughly len('content') // 4
    args, kwargs = strategy.acquire.call_args
    estimated = args[0] if args else kwargs.get('estimated_tokens')
    assert estimated == len('content') // 4


def test_provider_handler_calls_record_usage_on_success():
    from src.analyzers.provider_chain import ProviderHandler
    provider = MagicMock()
    strategy = MagicMock()
    result = _make_result()
    provider.analyze.return_value = result

    handler = ProviderHandler(provider=provider, strategy=strategy, priority=1, name='test')
    handler.analyze('content', 'prompt')

    strategy.record_usage.assert_called_once_with(
        result.input_tokens + result.output_tokens
    )


def test_provider_handler_skips_record_usage_on_none():
    from src.analyzers.provider_chain import ProviderHandler
    provider = MagicMock()
    strategy = MagicMock()
    provider.analyze.return_value = None

    handler = ProviderHandler(provider=provider, strategy=strategy, priority=1, name='test')
    result = handler.analyze('content', 'prompt')

    strategy.record_usage.assert_not_called()
    assert result is None


def test_provider_handler_returns_result():
    from src.analyzers.provider_chain import ProviderHandler
    provider = MagicMock()
    strategy = MagicMock()
    expected = _make_result()
    provider.analyze.return_value = expected

    handler = ProviderHandler(provider=provider, strategy=strategy, priority=1, name='test')
    result = handler.analyze('content', 'prompt')

    assert result is expected


def test_provider_chain_implements_llm_provider():
    from src.analyzers.provider_chain import ProviderChain
    from src.analyzers.providers.base_llm_provider import LLMProvider
    assert issubclass(ProviderChain, LLMProvider)


def test_provider_chain_returns_first_success():
    from src.analyzers.provider_chain import ProviderChain, ProviderHandler
    result = _make_result()
    h1 = MagicMock(spec=ProviderHandler)
    h1.priority = 1
    h1.name = 'first'
    h1.analyze.return_value = result

    h2 = MagicMock(spec=ProviderHandler)
    h2.priority = 2
    h2.name = 'second'

    chain = ProviderChain(handlers=[h2, h1])  # order shouldn't matter — sorted by priority
    outcome = chain.analyze('content', 'prompt')

    assert outcome is result
    h2.analyze.assert_not_called()  # h1 succeeded, h2 never tried


def test_provider_chain_falls_back_on_none():
    from src.analyzers.provider_chain import ProviderChain, ProviderHandler
    result = _make_result()

    h1 = MagicMock(spec=ProviderHandler)
    h1.priority = 1
    h1.name = 'first'
    h1.analyze.return_value = None  # failure

    h2 = MagicMock(spec=ProviderHandler)
    h2.priority = 2
    h2.name = 'second'
    h2.analyze.return_value = result  # success

    chain = ProviderChain(handlers=[h1, h2])
    outcome = chain.analyze('content', 'prompt')

    assert outcome is result
    h1.analyze.assert_called_once()
    h2.analyze.assert_called_once()


def test_provider_chain_falls_back_on_exception():
    from src.analyzers.provider_chain import ProviderChain, ProviderHandler
    result = _make_result()

    h1 = MagicMock(spec=ProviderHandler)
    h1.priority = 1
    h1.name = 'first'
    h1.analyze.side_effect = RuntimeError("API down")

    h2 = MagicMock(spec=ProviderHandler)
    h2.priority = 2
    h2.name = 'second'
    h2.analyze.return_value = result

    chain = ProviderChain(handlers=[h1, h2])
    outcome = chain.analyze('content', 'prompt')

    assert outcome is result


def test_provider_chain_falls_back_on_rate_limit_exhausted():
    from src.analyzers.provider_chain import ProviderChain, ProviderHandler
    from src.analyzers.strategies.leaky_bucket_strategy import RateLimitExhausted
    result = _make_result()

    h1 = MagicMock(spec=ProviderHandler)
    h1.priority = 1
    h1.name = 'first'
    h1.analyze.side_effect = RateLimitExhausted("daily cap hit")

    h2 = MagicMock(spec=ProviderHandler)
    h2.priority = 2
    h2.name = 'second'
    h2.analyze.return_value = result

    chain = ProviderChain(handlers=[h1, h2])
    outcome = chain.analyze('content', 'prompt')

    assert outcome is result


def test_provider_chain_returns_none_when_all_fail():
    from src.analyzers.provider_chain import ProviderChain, ProviderHandler

    h1 = MagicMock(spec=ProviderHandler)
    h1.priority = 1
    h1.name = 'first'
    h1.analyze.return_value = None

    h2 = MagicMock(spec=ProviderHandler)
    h2.priority = 2
    h2.name = 'second'
    h2.analyze.side_effect = RuntimeError("also down")

    chain = ProviderChain(handlers=[h1, h2])
    outcome = chain.analyze('content', 'prompt')

    assert outcome is None


def test_provider_chain_sorts_handlers_by_priority():
    from src.analyzers.provider_chain import ProviderChain, ProviderHandler

    h1 = MagicMock(spec=ProviderHandler)
    h1.priority = 2
    h1.name = 'lower'
    h1.analyze.return_value = None

    h2 = MagicMock(spec=ProviderHandler)
    h2.priority = 1
    h2.name = 'higher'
    h2.analyze.return_value = _make_result()

    # Pass in reverse order — chain must sort them
    chain = ProviderChain(handlers=[h1, h2])
    chain.analyze('content', 'prompt')

    h2.analyze.assert_called_once()  # priority=1 tried first
    h1.analyze.assert_not_called()   # priority=2 never needed
