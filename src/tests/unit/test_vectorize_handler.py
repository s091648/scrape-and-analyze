from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.infrastructure.vector_store.vectorize_handler import VectorizeHandler
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


def test_handle_calls_ingest():
    vector_store = MagicMock()
    handler = VectorizeHandler(vector_store)
    article = _make_article()
    event = ArticleProcessedEvent(article=article)

    handler.handle(event)

    vector_store.ingest.assert_called_once_with(article)


def test_handle_does_not_reraise_on_error():
    vector_store = MagicMock()
    vector_store.ingest.side_effect = RuntimeError("SDK failure")
    handler = VectorizeHandler(vector_store)
    article = _make_article()
    event = ArticleProcessedEvent(article=article)

    # Should not raise
    handler.handle(event)


def test_handle_logs_exception_on_error():
    vector_store = MagicMock()
    vector_store.ingest.side_effect = RuntimeError("SDK failure")
    handler = VectorizeHandler(vector_store)
    article = _make_article()
    event = ArticleProcessedEvent(article=article)

    with patch("src.infrastructure.vector_store.vectorize_handler.logger") as mock_logger:
        handler.handle(event)
        mock_logger.exception.assert_called_once()
        call_kwargs = mock_logger.exception.call_args
        assert "vectorize_failed" in call_kwargs[0] or "vectorize_failed" in str(call_kwargs)
