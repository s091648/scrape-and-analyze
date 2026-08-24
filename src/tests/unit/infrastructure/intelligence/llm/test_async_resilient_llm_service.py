import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata


def _make_result():
    content = AnalysisContent(tag_groups=[], pain_points='p', insights='i',
                               innovations='n', summary='s')
    metadata = AnalysisMetadata(model_used='test', input_tokens=100, output_tokens=50)
    return (content, metadata)


@pytest.mark.asyncio
async def test_async_provider_handler_calls_strategy_acquire():
    from src.infrastructure.intelligence.llm.resilient_llm_service import AsyncProviderHandler
    provider = MagicMock()
    provider.analyze = AsyncMock(return_value=_make_result())
    strategy = MagicMock()

    handler = AsyncProviderHandler(provider=provider, strategy=strategy, priority=1, name='test')
    result = await handler.analyze("content", "prompt")

    strategy.acquire.assert_called_once()
    assert result is not None


@pytest.mark.asyncio
async def test_async_resilient_llm_service_falls_back_to_next_provider():
    from src.infrastructure.intelligence.llm.resilient_llm_service import AsyncResilientLLMService, AsyncProviderHandler
    from src.infrastructure.intelligence.llm.rate_limit.no_op_strategy import NoOpStrategy

    provider1 = MagicMock()
    provider1.analyze = AsyncMock(return_value=None)  # first provider fails
    provider2 = MagicMock()
    provider2.analyze = AsyncMock(return_value=_make_result())

    handlers = [
        AsyncProviderHandler(provider=provider1, strategy=NoOpStrategy(), priority=1, name='p1'),
        AsyncProviderHandler(provider=provider2, strategy=NoOpStrategy(), priority=2, name='p2'),
    ]
    service = AsyncResilientLLMService(handlers=handlers)
    result = await service.analyze("content", "prompt")

    assert result is not None
    content, metadata = result
    assert content.pain_points == 'p'


@pytest.mark.asyncio
async def test_async_resilient_llm_service_moves_exhausted_provider_to_end_and_tracks_it():
    from src.infrastructure.intelligence.llm.resilient_llm_service import AsyncResilientLLMService, AsyncProviderHandler
    from src.infrastructure.intelligence.llm.rate_limit.no_op_strategy import NoOpStrategy
    from src.infrastructure.intelligence.llm.rate_limit import RateLimitExhausted

    provider1 = MagicMock()
    provider1.analyze = AsyncMock(side_effect=RateLimitExhausted("daily cap hit"))
    provider2 = MagicMock()
    provider2.analyze = AsyncMock(return_value=_make_result())

    handlers = [
        AsyncProviderHandler(provider=provider1, strategy=NoOpStrategy(), priority=1, name='p1'),
        AsyncProviderHandler(provider=provider2, strategy=NoOpStrategy(), priority=2, name='p2'),
    ]
    service = AsyncResilientLLMService(handlers=handlers)

    result = await service.analyze("content", "prompt")
    assert result is not None
    assert 'p1' in service.exhausted_providers

    # p1 was moved to the end of the internal handler list — a second call
    # should try p2 first without even touching the exhausted p1 again.
    provider1.analyze.reset_mock()
    result2 = await service.analyze("content", "prompt")
    assert result2 is not None
    provider1.analyze.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_resilient_llm_service_returns_none_when_all_providers_fail():
    from src.infrastructure.intelligence.llm.resilient_llm_service import AsyncResilientLLMService, AsyncProviderHandler
    from src.infrastructure.intelligence.llm.rate_limit.no_op_strategy import NoOpStrategy

    provider = MagicMock()
    provider.analyze = AsyncMock(return_value=None)

    handlers = [AsyncProviderHandler(provider=provider, strategy=NoOpStrategy(), priority=1, name='p1')]
    service = AsyncResilientLLMService(handlers=handlers)

    result = await service.analyze("content", "prompt")
    assert result is None


@pytest.mark.asyncio
async def test_concurrent_analyze_calls_hitting_same_exhausted_provider_do_not_raise():
    """US3 T051: confirms concurrent article tasks that all hit
    RateLimitExhausted on the same top-priority handler near-simultaneously
    (a real network round-trip's 429 response is a genuine suspension point,
    modeled here with asyncio.sleep(0) so the tasks truly interleave rather
    than running one at a time) don't crash the shared handler-reorder, and
    exhausted_providers reports the provider exactly once. The remove()/
    append() pair has no `await` between them (research.md item 7), so a
    concurrent remover always finds the handler still present — this is a
    confirmation test, not a regression test for a bug that was found."""
    from src.infrastructure.intelligence.llm.resilient_llm_service import AsyncResilientLLMService, AsyncProviderHandler
    from src.infrastructure.intelligence.llm.rate_limit.no_op_strategy import NoOpStrategy
    from src.infrastructure.intelligence.llm.rate_limit import RateLimitExhausted

    async def _raise_after_yield(*args, **kwargs):
        await asyncio.sleep(0)
        raise RateLimitExhausted("daily cap hit")

    provider1 = MagicMock()
    provider1.analyze = AsyncMock(side_effect=_raise_after_yield)
    provider2 = MagicMock()
    provider2.analyze = AsyncMock(return_value=_make_result())

    handlers = [
        AsyncProviderHandler(provider=provider1, strategy=NoOpStrategy(), priority=1, name='p1'),
        AsyncProviderHandler(provider=provider2, strategy=NoOpStrategy(), priority=2, name='p2'),
    ]
    service = AsyncResilientLLMService(handlers=handlers)

    # All N concurrent calls snapshot [p1, p2] before any of them reorders
    # the shared list — every one hits RateLimitExhausted on p1.
    results = await asyncio.gather(
        *(service.analyze("content", "prompt") for _ in range(10)),
        return_exceptions=True,
    )

    assert all(not isinstance(r, Exception) for r in results), results
    assert all(r is not None for r in results)
    assert service.exhausted_providers == ['p1']


@pytest.mark.asyncio
async def test_exhausted_providers_lists_every_model_hit_during_concurrent_dispatch():
    """US4 T062 (FR-012): with a pool of providers each having a small rpd,
    a burst of concurrent analyze() calls that exceeds the pool's combined
    daily capacity must leave exhausted_providers reporting every provider
    that actually hit its cap — not just the first one tried."""
    from src.infrastructure.intelligence.llm.resilient_llm_service import AsyncResilientLLMService, AsyncProviderHandler
    from src.infrastructure.intelligence.llm.rate_limit import SlidingWindowStrategy

    def _make_handler(name, priority, rpd):
        provider = MagicMock()

        async def _analyze(content, prompt):
            await asyncio.sleep(0)
            return _make_result()
        provider.analyze = AsyncMock(side_effect=_analyze)
        strategy = SlidingWindowStrategy(rpm=1000, tpm=1_000_000, rpd=rpd)
        return AsyncProviderHandler(provider=provider, strategy=strategy, priority=priority, name=name)

    p1 = _make_handler("p1", priority=1, rpd=2)
    p2 = _make_handler("p2", priority=2, rpd=2)
    service = AsyncResilientLLMService(handlers=[p1, p2])

    # 6 concurrent calls against a 4-slot pool (2+2) — both providers must
    # exhaust their daily cap.
    results = await asyncio.gather(*(service.analyze("content", "prompt") for _ in range(6)))

    assert sum(1 for r in results if r is not None) == 4
    assert sum(1 for r in results if r is None) == 2
    assert service.exhausted_providers == ["p1", "p2"]


@pytest.mark.asyncio
async def test_async_resilient_embedding_service_falls_back_to_next_provider():
    from src.infrastructure.intelligence.llm.resilient_llm_service import (
        AsyncResilientEmbeddingService, AsyncEmbeddingProviderHandler,
    )
    from src.infrastructure.intelligence.llm.rate_limit.no_op_strategy import NoOpStrategy

    provider1 = MagicMock()
    provider1.count_tokens = AsyncMock(return_value=5)
    provider1.embed = AsyncMock(return_value=None)
    provider2 = MagicMock()
    provider2.count_tokens = AsyncMock(return_value=5)
    provider2.embed = AsyncMock(return_value=[0.1, 0.2])

    handlers = [
        AsyncEmbeddingProviderHandler(provider=provider1, strategy=NoOpStrategy(), priority=1, name='e1'),
        AsyncEmbeddingProviderHandler(provider=provider2, strategy=NoOpStrategy(), priority=2, name='e2'),
    ]
    service = AsyncResilientEmbeddingService(handlers=handlers)
    result = await service.embed("text")

    assert result == [0.1, 0.2]
