from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.modules.intelligence.application.event_handlers.rag_ingestion_handler import RagIngestionHandler
from src.modules.intelligence.application.events.rag_ingestion_failed import RagIngestionFailedEvent
from src.modules.intelligence.application.use_cases.ingest_article_for_rag import IngestArticleForRagUseCase
from src.shared.application.events.article_processed import ArticleProcessedEvent
from src.shared.domain.entities.article import Article


def _make_article():
    return Article(
        id=uuid4(),
        url="https://example.com/article",
        url_hash="abc123",
        source="rss",
        title="Test Article",
        content="This is the full text of the article.",
    )


def _make_handler(use_case=None):
    use_case = use_case or MagicMock(spec=IngestArticleForRagUseCase)
    event_bus = MagicMock()
    return RagIngestionHandler(use_case, event_bus), event_bus


def test_handle_calls_use_case():
    use_case = MagicMock(spec=IngestArticleForRagUseCase)
    handler, _ = _make_handler(use_case)
    article = _make_article()
    event = ArticleProcessedEvent(article=article, full_text="Full PDF text here.")

    handler.handle(event)

    use_case.execute.assert_called_once_with(article, "Full PDF text here.")


def test_handle_does_not_reraise_on_error():
    use_case = MagicMock(spec=IngestArticleForRagUseCase)
    use_case.execute.side_effect = RuntimeError("SDK failure")
    handler, _ = _make_handler(use_case)
    article = _make_article()
    event = ArticleProcessedEvent(article=article, full_text="some text")

    # Should not raise — pipeline must continue
    handler.handle(event)


def test_handle_logs_exception_on_error():
    use_case = MagicMock(spec=IngestArticleForRagUseCase)
    use_case.execute.side_effect = RuntimeError("SDK failure")
    handler, _ = _make_handler(use_case)
    article = _make_article()
    event = ArticleProcessedEvent(article=article, full_text="some text")

    with patch("src.modules.intelligence.application.event_handlers.rag_ingestion_handler.logger") as mock_logger:
        handler.handle(event)
        mock_logger.exception.assert_called_once()
        assert "rag_ingest_failed" in str(mock_logger.exception.call_args)


def test_handle_publishes_failed_event_on_error():
    use_case = MagicMock(spec=IngestArticleForRagUseCase)
    use_case.execute.side_effect = RuntimeError("SDK failure")
    handler, event_bus = _make_handler(use_case)
    article = _make_article()
    event = ArticleProcessedEvent(article=article, full_text="some text")

    handler.handle(event)

    event_bus.publish.assert_called_once()
    published = event_bus.publish.call_args[0][0]
    assert isinstance(published, RagIngestionFailedEvent)
    assert published.article_id == article.id
    assert published.article_url == article.url
    assert published.task_type == "rag_ingest"
    assert published.exception_type == "RuntimeError"


def test_handle_does_not_publish_on_success():
    use_case = MagicMock(spec=IngestArticleForRagUseCase)
    handler, event_bus = _make_handler(use_case)
    article = _make_article()
    event = ArticleProcessedEvent(article=article, full_text="some text")

    handler.handle(event)

    event_bus.publish.assert_not_called()
