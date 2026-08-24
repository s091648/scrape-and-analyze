from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.intelligence.application.event_handlers.rag_ingestion_handler import AsyncRagIngestionHandler
from src.modules.intelligence.application.events.rag_ingestion_failed import RagIngestionFailedEvent
from src.modules.intelligence.application.use_cases.ingest_article_for_rag import AsyncIngestArticleForRagUseCase
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
    use_case = use_case or MagicMock(spec=AsyncIngestArticleForRagUseCase)
    if not isinstance(use_case.execute, AsyncMock):
        use_case.execute = AsyncMock()
    event_bus = MagicMock()
    event_bus.publish = AsyncMock()
    return AsyncRagIngestionHandler(use_case, event_bus), event_bus


@pytest.mark.asyncio
async def test_async_handle_calls_use_case():
    use_case = MagicMock(spec=AsyncIngestArticleForRagUseCase)
    use_case.execute = AsyncMock()
    handler, _ = _make_handler(use_case)
    article = _make_article()
    event = ArticleProcessedEvent(article=article, full_text="Full PDF text here.")

    await handler.handle(event)

    use_case.execute.assert_awaited_once_with(article, "Full PDF text here.")


@pytest.mark.asyncio
async def test_async_handle_does_not_reraise_on_error():
    use_case = MagicMock(spec=AsyncIngestArticleForRagUseCase)
    use_case.execute = AsyncMock(side_effect=RuntimeError("SDK failure"))
    handler, _ = _make_handler(use_case)
    article = _make_article()
    event = ArticleProcessedEvent(article=article, full_text="some text")

    # Should not raise — the article's task must continue
    await handler.handle(event)


@pytest.mark.asyncio
async def test_async_handle_publishes_failed_event_on_error():
    use_case = MagicMock(spec=AsyncIngestArticleForRagUseCase)
    use_case.execute = AsyncMock(side_effect=RuntimeError("SDK failure"))
    handler, event_bus = _make_handler(use_case)
    article = _make_article()
    event = ArticleProcessedEvent(article=article, full_text="some text")

    await handler.handle(event)

    event_bus.publish.assert_awaited_once()
    published = event_bus.publish.call_args[0][0]
    assert isinstance(published, RagIngestionFailedEvent)
    assert published.article_id == article.id
    assert published.exception_type == "RuntimeError"


@pytest.mark.asyncio
async def test_async_handle_does_not_publish_on_success():
    use_case = MagicMock(spec=AsyncIngestArticleForRagUseCase)
    use_case.execute = AsyncMock()
    handler, event_bus = _make_handler(use_case)
    article = _make_article()
    event = ArticleProcessedEvent(article=article, full_text="some text")

    await handler.handle(event)

    event_bus.publish.assert_not_awaited()
