from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.infrastructure.intelligence.vector_store.rag_sdk_ingestion_impl import AsyncRagSdkIngestionService
from src.shared.domain.entities.article import Article


def _make_article(content="Full article text here."):
    return Article(
        id=uuid4(),
        url="https://example.com/paper",
        url_hash="def456",
        source="arxiv",
        title="Some Paper",
        content=content,
    )


@pytest.mark.asyncio
async def test_async_ingest_awaits_processor_directly_with_provided_full_text():
    processor = MagicMock()
    processor.ingest = AsyncMock()
    service = AsyncRagSdkIngestionService(processor)
    article = _make_article()
    full_text = "Title\n\nAbstract text\n\n## Introduction\nIntro body"

    await service.ingest(article, full_text)

    processor.ingest.assert_awaited_once_with(
        full_text=full_text,
        articles_column_values={
            "url": str(article.url),
            "title": article.title,
            "source": article.source,
            "public_article_id": str(article.id),
            "topic_id": None,
        },
    )


@pytest.mark.asyncio
async def test_async_ingest_includes_topic_id_when_present():
    processor = MagicMock()
    processor.ingest = AsyncMock()
    service = AsyncRagSdkIngestionService(processor)
    topic_id = uuid4()
    article = _make_article()
    article.topic_id = topic_id

    await service.ingest(article, "some text")

    _, kwargs = processor.ingest.call_args
    assert kwargs["articles_column_values"]["topic_id"] == str(topic_id)
