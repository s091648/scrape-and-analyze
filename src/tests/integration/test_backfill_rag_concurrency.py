"""
Integration tests: src/entrypoints/cli/backfill_rag.py's concurrent article
ingestion shares one EmbeddingBatchCoordinator/rate limiter instance per run
(024-async-pipeline-refactor US6, research.md item 11) — replaces the
previous asyncio.to_thread + thread-bounded semaphore model, which gave each
concurrent article its own event loop and couldn't share the coordinator.
Mocks the DB backend and dense embedding provider (no real DB/network), same
convention as test_rag_ingestion_pipeline.py.
"""
import uuid
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock

from chatbot_plugin_sdk import IngestProcessor
from src.entrypoints.cli.backfill_rag import _run_backfill
from src.infrastructure.intelligence.vector_store.rag_sdk_ingestion_impl import AsyncRagSdkIngestionService
from src.modules.intelligence.application.use_cases.ingest_article_for_rag import AsyncIngestArticleForRagUseCase
from src.shared.domain.entities.article import Article


def _make_article() -> Article:
    return Article(
        id=uuid4(),
        url=f"https://example.com/article/{uuid4()}",
        url_hash=str(uuid4()).replace("-", "")[:32],
        source="arxiv",
        title="Backfill Concurrency Test Article",
        content="word " * 100,
    )


class _RecordingDenseProvider:
    dimension = 3

    def __init__(self) -> None:
        self.embed_calls = 0

    async def embed(self, texts):
        self.embed_calls += 1
        return [[0.1, 0.2, 0.3] for _ in texts]


def _build_use_case(dense):
    backend = AsyncMock()
    processor = IngestProcessor()
    processor.configure(backend=backend, dense=dense, embed_batch_size=16)
    service = AsyncRagSdkIngestionService(processor)
    return AsyncIngestArticleForRagUseCase(service), processor, backend


@pytest.mark.integration
class TestBackfillRagConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_backfill_articles_all_succeed_and_coordinator_closes(self):
        dense = _RecordingDenseProvider()
        use_case, processor, backend = _build_use_case(dense)

        articles = [_make_article() for _ in range(5)]
        succeeded, failed = await _run_backfill(articles, use_case, concurrency=3)

        assert succeeded == 5
        assert failed == 0
        assert backend.upsert.call_count == 5
        # _run_backfill() closes the coordinator on the same loop it ran on —
        # EmbeddingBatchCoordinator.aclose() clears _worker_task only after
        # successfully cancelling it, so None here proves aclose() reached the
        # worker task the concurrent articles shared (not just that it existed).
        assert processor._dense_coordinator._worker_task is None

    @pytest.mark.asyncio
    async def test_aclose_still_runs_when_one_article_fails(self):
        dense = _RecordingDenseProvider()
        use_case, processor, backend = _build_use_case(dense)

        good_article = _make_article()
        bad_article = _make_article()
        bad_article_id = uuid.uuid5(uuid.NAMESPACE_URL, str(bad_article.url))

        async def _selective_upsert(article_id, *args, **kwargs):
            if article_id == bad_article_id:
                raise RuntimeError("boom")

        backend.upsert = AsyncMock(side_effect=_selective_upsert)

        succeeded, failed = await _run_backfill([good_article, bad_article], use_case, concurrency=2)

        assert succeeded == 1
        assert failed == 1
        assert processor._dense_coordinator._worker_task is None
