"""
Integration tests for the vectorization pipeline.

These tests use the real DB schema but mock the RAG SDK processor
to avoid needing the actual embedding service.
"""
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.infrastructure.vector_store.rag_sdk_vector_store_impl import RagSdkVectorStoreService
from src.infrastructure.vector_store.vectorize_handler import VectorizeHandler
from src.shared.application.events.article_processed import ArticleProcessedEvent
from src.shared.domain.entities.article import Article


def _make_article():
    return Article(
        id=uuid4(),
        url=f"https://example.com/article/{uuid4()}",
        url_hash=str(uuid4()).replace("-", "")[:32],
        source="rss",
        title="Integration Test Article",
        content="This is test content for the vectorization integration test.",
    )


@pytest.mark.integration
class TestVectorizationPipeline:
    def test_handler_subscribes_and_fires(self):
        processor = MagicMock()
        service = RagSdkVectorStoreService(processor)
        handler = VectorizeHandler(service)
        article = _make_article()
        event = ArticleProcessedEvent(article=article)

        handler.handle(event)

        processor.ingest.assert_called_once()
        _, kwargs = processor.ingest.call_args
        assert kwargs["metadata"]["article_id"] == str(article.id)

    def test_idempotent_ingest_does_not_raise(self):
        """Same article ingested twice should not raise (SDK handles UNIQUE constraint)."""
        processor = MagicMock()
        service = RagSdkVectorStoreService(processor)
        handler = VectorizeHandler(service)
        article = _make_article()
        event = ArticleProcessedEvent(article=article)

        handler.handle(event)
        handler.handle(event)

        assert processor.ingest.call_count == 2

    def test_sdk_failure_does_not_propagate(self):
        processor = MagicMock()
        processor.ingest.side_effect = Exception("DB connection error")
        service = RagSdkVectorStoreService(processor)
        handler = VectorizeHandler(service)
        article = _make_article()
        event = ArticleProcessedEvent(article=article)

        # Must not raise — pipeline must continue
        handler.handle(event)
