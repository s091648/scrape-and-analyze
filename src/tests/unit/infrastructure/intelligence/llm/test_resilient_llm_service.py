import pytest
from unittest.mock import MagicMock
from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata


def _make_result():
    content = AnalysisContent(tag_groups=[], pain_points='p', insights='i',
                               innovations='n', summary='s')
    metadata = AnalysisMetadata(model_used='test', input_tokens=100, output_tokens=50)
    return (content, metadata)


def test_provider_handler_calls_strategy_acquire():
    from src.infrastructure.intelligence.llm.resilient_llm_service import ProviderHandler
    from src.infrastructure.intelligence.llm.rate_limit.no_op_strategy import NoOpStrategy
    provider = MagicMock()
    strategy = MagicMock()
    provider.analyze.return_value = _make_result()

    handler = ProviderHandler(provider=provider, strategy=strategy, priority=1, name='test')
    result = handler.analyze("content", "prompt")

    strategy.acquire.assert_called_once()
    assert result is not None


def test_resilient_llm_service_falls_back_to_next_provider():
    from src.infrastructure.intelligence.llm.resilient_llm_service import ResilientLLMService, ProviderHandler
    from src.infrastructure.intelligence.llm.rate_limit.no_op_strategy import NoOpStrategy

    provider1 = MagicMock()
    provider1.analyze.return_value = None  # first provider fails
    provider2 = MagicMock()
    provider2.analyze.return_value = _make_result()

    handlers = [
        ProviderHandler(provider=provider1, strategy=NoOpStrategy(), priority=1, name='p1'),
        ProviderHandler(provider=provider2, strategy=NoOpStrategy(), priority=2, name='p2'),
    ]
    service = ResilientLLMService(handlers=handlers)
    result = service.analyze("content", "prompt")

    assert result is not None
    content, metadata = result
    assert content.pain_points == 'p'