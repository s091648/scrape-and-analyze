"""US3 (024-async-pipeline-refactor) T053: PipelineStats.record() and
RateLimitedProviderTracker.mark_exhausted() must stay correct when many
concurrently-running article asyncio.Tasks call them — both already use a
threading.Lock internally (safe even though there's only one OS thread here,
since it also guards against unlucky interleaving if the GIL were ever
released mid-mutation); this test confirms no count is lost/double-counted
under real asyncio.gather concurrency, not just by code inspection."""
import asyncio

import pytest

from src.modules.collection.application.use_cases import PipelineStats, ArticleOutcome
from src.infrastructure.shared.rate_limit_tracker import RateLimitedProviderTracker


@pytest.mark.asyncio
async def test_pipeline_stats_record_is_correct_under_concurrent_callers():
    stats = PipelineStats()
    N = 200

    async def _record(i: int) -> None:
        await asyncio.sleep(0)  # forces real interleaving between callers
        outcome = ArticleOutcome.NEW if i % 3 == 0 else (
            ArticleOutcome.DUPLICATE if i % 3 == 1 else ArticleOutcome.FAILED
        )
        stats.record("rss", outcome)

    await asyncio.gather(*(_record(i) for i in range(N)))

    results = stats.get_results()
    assert len(results) == 1
    total = results[0].new + results[0].duplicate + results[0].failed
    assert total == N
    assert results[0].new == sum(1 for i in range(N) if i % 3 == 0)
    assert results[0].duplicate == sum(1 for i in range(N) if i % 3 == 1)
    assert results[0].failed == sum(1 for i in range(N) if i % 3 == 2)


@pytest.mark.asyncio
async def test_rate_limited_provider_tracker_mark_exhausted_is_correct_under_concurrent_callers():
    tracker = RateLimitedProviderTracker()
    provider_names = [f"provider-{i % 5}" for i in range(50)]  # 5 distinct names, repeated

    async def _mark(name: str) -> None:
        await asyncio.sleep(0)
        tracker.mark_exhausted(name)

    await asyncio.gather(*(_mark(name) for name in provider_names))

    assert tracker.exhausted == sorted(set(provider_names))
