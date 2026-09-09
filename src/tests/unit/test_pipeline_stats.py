"""US3 (024-async-pipeline-refactor) T053: PipelineStats.record() and
RateLimitedProviderTracker.mark_exhausted() must stay correct when many
concurrently-running article asyncio.Tasks call them — both already use a
threading.Lock internally (safe even though there's only one OS thread here,
since it also guards against unlucky interleaving if the GIL were ever
released mid-mutation); this test confirms no count is lost/double-counted
under real asyncio.gather concurrency, not just by code inspection."""
import asyncio
import uuid

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


def test_record_partial_failure_counts_distinct_articles_and_ignores_none():
    """fix/scraper_failure: an article that was saved (counted `new`) but later
    failed analysis / tag normalization / translation / RAG is a *partial*
    failure — tracked separately from `failed` (never persisted). The same
    article failing several downstream stages, or a RAG failure arriving from a
    separate bus after the text stage, must not double-count; a FailedEvent with
    no article id is a no-op."""
    stats = PipelineStats()
    a1, a2 = uuid.uuid4(), uuid.uuid4()

    assert stats.partial_failure_count == 0

    stats.record_partial_failure(a1)
    stats.record_partial_failure(a1)  # same article, second failed stage
    stats.record_partial_failure(a2)
    stats.record_partial_failure(None)  # FailedEvent carrying no article id

    assert stats.partial_failure_count == 2


@pytest.mark.asyncio
async def test_record_partial_failure_is_correct_under_concurrent_callers():
    stats = PipelineStats()
    ids = [uuid.uuid4() for _ in range(20)]

    async def _mark(article_id):
        await asyncio.sleep(0)
        # each id recorded 5x concurrently — must still collapse to one
        for _ in range(5):
            stats.record_partial_failure(article_id)

    await asyncio.gather(*(_mark(i) for i in ids))

    assert stats.partial_failure_count == 20


@pytest.mark.asyncio
async def test_rate_limited_provider_tracker_mark_exhausted_is_correct_under_concurrent_callers():
    tracker = RateLimitedProviderTracker()
    provider_names = [f"provider-{i % 5}" for i in range(50)]  # 5 distinct names, repeated

    async def _mark(name: str) -> None:
        await asyncio.sleep(0)
        tracker.mark_exhausted(name)

    await asyncio.gather(*(_mark(name) for name in provider_names))

    assert tracker.exhausted == sorted(set(provider_names))
