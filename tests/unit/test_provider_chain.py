import pytest
from unittest.mock import MagicMock, call
from src.analyzers.llm_provider import AnalysisResult


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
