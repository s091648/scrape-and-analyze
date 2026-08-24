"""US4 (024-async-pipeline-refactor) tests for the ProviderSelector port and
its wiring into AsyncResilientLLMService — concurrent analyze/translate/
generate calls should spread across every registered model with spare
capacity instead of all queuing behind the single highest-priority one.

T059: concurrent calls spread across multiple models once the top-priority
      one's per-minute window is full.
T060: a momentarily-throttled model is skipped this round, but not
      permanently excluded — once its window clears, it's tried again.
T061: a stress test of many concurrent reservation attempts against a
      single-provider pool never double-counts or drops a reservation.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.intelligence.llm.resilient_llm_service import AsyncResilientLLMService, AsyncProviderHandler
from src.infrastructure.intelligence.llm.rate_limit import SlidingWindowStrategy, PriorityFirstProviderSelector


def _make_result():
    from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata
    content = AnalysisContent(tag_groups=[], pain_points='p', insights='i', innovations='n', summary='s')
    metadata = AnalysisMetadata(model_used='test', input_tokens=10, output_tokens=5)
    return (content, metadata)


def _make_handler(name: str, priority: int, **strategy_kwargs) -> AsyncProviderHandler:
    provider = MagicMock()
    provider.analyze = AsyncMock(return_value=_make_result())
    strategy = SlidingWindowStrategy(rpm=strategy_kwargs.get("rpm", 1000),
                                      tpm=strategy_kwargs.get("tpm", 1_000_000),
                                      rpd=strategy_kwargs.get("rpd", 1000))
    return AsyncProviderHandler(provider=provider, strategy=strategy, priority=priority, name=name)


# ---------------------------------------------------------------------------
# T059: concurrent calls spread across models once the top one's RPM is full
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_calls_spread_across_models_once_top_priority_rpm_is_full():
    p1 = _make_handler("p1", priority=1, rpm=2)   # only 2 requests/min
    p2 = _make_handler("p2", priority=2, rpm=100)  # plenty of headroom
    service = AsyncResilientLLMService(handlers=[p1, p2])

    calls_per_provider = {"p1": 0, "p2": 0}

    def _track(name, real_analyze):
        async def _wrapped(content, prompt):
            calls_per_provider[name] += 1
            return await real_analyze(content, prompt)
        return _wrapped

    p1.provider.analyze = _track("p1", p1.provider.analyze)
    p2.provider.analyze = _track("p2", p2.provider.analyze)

    results = await asyncio.gather(*(service.analyze("content", "prompt") for _ in range(4)))

    assert all(r is not None for r in results)
    # p1's RPM window only fits 2 — the other 2 calls must have been routed
    # to p2 instead of blocking on p1 (has_capacity() steered dispatch away).
    assert calls_per_provider["p1"] == 2
    assert calls_per_provider["p2"] == 2


# ---------------------------------------------------------------------------
# T060: momentary RPM throttling skips a model this round, doesn't exclude it
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_throttled_model_is_skipped_but_not_permanently_excluded():
    p1 = _make_handler("p1", priority=1, rpm=1)  # only 1 request/min
    p2 = _make_handler("p2", priority=2, rpm=100)
    service = AsyncResilientLLMService(handlers=[p1, p2])

    # First call: p1 has capacity, gets used.
    await service.analyze("content", "prompt")
    p1.provider.analyze.assert_awaited_once()

    # Second call: p1's window is full (no RateLimitExhausted — just RPM
    # throttling, FR-010) — must be skipped in favor of p2, not block.
    p2_analyze_before = p2.provider.analyze.await_count
    await service.analyze("content", "prompt")
    assert p2.provider.analyze.await_count == p2_analyze_before + 1

    # p1 must NOT have been reordered to the end (RateLimitExhausted's
    # remove()/append() never fired — this was RPM throttling, not a daily
    # cap hit) — it's still first in priority order.
    assert service._handlers[0].name == "p1"

    # Once its window clears, p1 is tried again (not permanently excluded).
    p1.strategy._rpm_window.clear()
    p1_analyze_before = p1.provider.analyze.await_count
    await service.analyze("content", "prompt")
    assert p1.provider.analyze.await_count == p1_analyze_before + 1


# ---------------------------------------------------------------------------
# T061: stress test — no reservation double-counted or dropped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_reservations_never_double_counted_or_dropped():
    N = 50
    p1 = _make_handler("p1", priority=1, rpd=N)  # exactly N slots for the day

    async def _slow_analyze(content, prompt):
        await asyncio.sleep(0)  # forces real interleaving mid-dispatch
        return _make_result()
    p1.provider.analyze = AsyncMock(side_effect=_slow_analyze)

    service = AsyncResilientLLMService(handlers=[p1])

    # N+1 concurrent calls against exactly N slots: double-counting would
    # cause MORE than one failure (early false-positive exhaustion), dropping
    # a reservation would let all N+1 succeed (exceeding the daily cap) —
    # correct accounting means exactly one call is turned away.
    results = await asyncio.gather(*(service.analyze("content", "prompt") for _ in range(N + 1)))

    succeeded = [r for r in results if r is not None]
    failed = [r for r in results if r is None]
    assert len(succeeded) == N
    assert len(failed) == 1


# ---------------------------------------------------------------------------
# PriorityFirstProviderSelector unit-level behavior
# ---------------------------------------------------------------------------

def test_priority_first_selector_filters_to_capacity_preserving_order():
    p1 = _make_handler("p1", priority=1, rpm=1)
    p2 = _make_handler("p2", priority=2)
    p3 = _make_handler("p3", priority=3)
    p1.strategy.acquire(estimated_tokens=1)  # exhausts p1's single RPM slot

    selector = PriorityFirstProviderSelector()
    selected = selector.select([p1, p2, p3])

    assert selected == [1, 2]  # p1 (index 0) filtered out, p2/p3 kept in order


def test_priority_first_selector_returns_empty_when_pool_saturated():
    p1 = _make_handler("p1", priority=1, rpm=1)
    p1.strategy.acquire(estimated_tokens=1)

    selector = PriorityFirstProviderSelector()
    assert selector.select([p1]) == []
