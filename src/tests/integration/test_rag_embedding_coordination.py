"""
Integration tests: RAG embedding calls are coordinated through one shared
EmbeddingBatchCoordinator when multiple articles' ingestion runs concurrently
(024-async-pipeline-refactor US6, research.md item 11) — a large article's
chunk count must not starve or collide with other concurrently-ingesting
articles against the shared embedding rate limit. Mocks the DB backend and
dense embedding provider (no real DB/network), same convention as
test_rag_ingestion_pipeline.py.
"""
import asyncio
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock

from chatbot_plugin_sdk import IngestProcessor
from src.infrastructure.intelligence.vector_store.rag_sdk_ingestion_impl import AsyncRagSdkIngestionService
from src.modules.intelligence.application.use_cases.ingest_article_for_rag import AsyncIngestArticleForRagUseCase
from src.shared.domain.entities.article import Article


def _make_article(content_len: int) -> Article:
    return Article(
        id=uuid4(),
        url=f"https://example.com/article/{uuid4()}",
        url_hash=str(uuid4()).replace("-", "")[:32],
        source="arxiv",
        title="Coordination Test Article",
        content="word " * content_len,
    )


class _RecordingDenseProvider:
    """Fake DenseEmbeddingProvider that records how many texts each call carried."""

    dimension = 3

    def __init__(self) -> None:
        self.call_sizes: list[int] = []

    async def embed(self, texts):
        self.call_sizes.append(len(texts))
        return [[0.1, 0.2, 0.3] for _ in texts]


def _build_use_case(dense, embed_batch_size: int = 8):
    backend = AsyncMock()
    processor = IngestProcessor()
    processor.configure(
        backend=backend, dense=dense, embed_batch_size=embed_batch_size,
        chunk_size=50, chunk_overlap=5,
    )
    service = AsyncRagSdkIngestionService(processor)
    return AsyncIngestArticleForRagUseCase(service), processor, backend


@pytest.mark.integration
class TestRagEmbeddingCoordination:
    @pytest.mark.asyncio
    async def test_small_and_large_article_ingested_concurrently_both_succeed(self):
        dense = _RecordingDenseProvider()
        use_case, processor, backend = _build_use_case(dense)

        small_article = _make_article(content_len=20)
        large_article = _make_article(content_len=2000)  # far more chunks than embed_batch_size

        results = await asyncio.gather(
            use_case.execute(small_article, full_text=small_article.content),
            use_case.execute(large_article, full_text=large_article.content),
            return_exceptions=True,
        )

        for r in results:
            assert not isinstance(r, BaseException), f"ingestion failed: {r!r}"
        assert backend.upsert.call_count == 2
        await processor.aclose()

    @pytest.mark.asyncio
    async def test_large_article_chunks_do_not_all_land_in_one_call(self):
        """The large article alone produces far more chunks than embed_batch_size —
        confirms the coordinator still splits one caller's own oversized submission
        into multiple provider calls (parity with the pre-coordinator behavior),
        not just when mixed with other concurrent callers."""
        dense = _RecordingDenseProvider()
        use_case, processor, backend = _build_use_case(dense, embed_batch_size=8)

        large_article = _make_article(content_len=2000)
        await use_case.execute(large_article, full_text=large_article.content)

        assert len(dense.call_sizes) > 1
        assert all(size <= 8 for size in dense.call_sizes)
        await processor.aclose()

    @pytest.mark.asyncio
    async def test_large_article_does_not_prevent_small_concurrent_articles_from_completing(self):
        dense = _RecordingDenseProvider()
        use_case, processor, backend = _build_use_case(dense, embed_batch_size=4)

        big = _make_article(content_len=3000)
        smalls = [_make_article(content_len=15) for _ in range(3)]

        results = await asyncio.gather(
            use_case.execute(big, full_text=big.content),
            *(use_case.execute(a, full_text=a.content) for a in smalls),
            return_exceptions=True,
        )

        for r in results:
            assert not isinstance(r, BaseException), f"ingestion failed: {r!r}"
        assert backend.upsert.call_count == 4
        await processor.aclose()
