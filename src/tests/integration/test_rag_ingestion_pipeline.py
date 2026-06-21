"""
Integration tests for the RAG ingestion pipeline.

These tests use the real DB schema but mock the RAG SDK processor
to avoid needing the actual embedding service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.infrastructure.intelligence.vector_store.rag_sdk_ingestion_impl import RagSdkIngestionService
from src.modules.intelligence.application.event_handlers.rag_ingestion_handler import RagIngestionHandler
from src.modules.intelligence.application.events.rag_ingestion_failed import RagIngestionFailedEvent
from src.modules.intelligence.application.use_cases.ingest_article_for_rag import IngestArticleForRagUseCase
from src.shared.application.events.article_processed import ArticleProcessedEvent
from src.shared.domain.entities.article import Article


def _make_article():
    return Article(
        id=uuid4(),
        url=f"https://example.com/article/{uuid4()}",
        url_hash=str(uuid4()).replace("-", "")[:32],
        source="rss",
        title="Integration Test Article",
        content="This is test content for the RAG ingestion integration test.",
    )


def _make_handler(processor):
    service = RagSdkIngestionService(processor)
    use_case = IngestArticleForRagUseCase(service)
    event_bus = MagicMock()
    handler = RagIngestionHandler(use_case, event_bus)
    return handler, event_bus


@pytest.mark.integration
class TestRagIngestionPipeline:
    def test_handler_subscribes_and_fires(self):
        processor = MagicMock()
        processor.ingest = AsyncMock()
        handler, _ = _make_handler(processor)
        article = _make_article()
        event = ArticleProcessedEvent(article=article)

        handler.handle(event)

        processor.ingest.assert_called_once()
        _, kwargs = processor.ingest.call_args
        assert kwargs["articles_column_values"]["url"] == str(article.url)

    def test_idempotent_ingest_does_not_raise(self):
        """Same article ingested twice should not raise (SDK handles UNIQUE constraint)."""
        processor = MagicMock()
        processor.ingest = AsyncMock()
        handler, _ = _make_handler(processor)
        article = _make_article()
        event = ArticleProcessedEvent(article=article)

        handler.handle(event)
        handler.handle(event)

        assert processor.ingest.call_count == 2

    def test_sdk_failure_publishes_failed_event(self):
        processor = MagicMock()
        processor.ingest = AsyncMock(side_effect=Exception("DB connection error"))
        handler, event_bus = _make_handler(processor)
        article = _make_article()
        event = ArticleProcessedEvent(article=article)

        # Must not raise — pipeline must continue
        handler.handle(event)

        event_bus.publish.assert_called_once()
        published = event_bus.publish.call_args[0][0]
        assert isinstance(published, RagIngestionFailedEvent)
        assert published.article_id == article.id
