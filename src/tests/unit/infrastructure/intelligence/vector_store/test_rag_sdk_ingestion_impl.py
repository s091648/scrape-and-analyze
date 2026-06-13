from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.infrastructure.intelligence.vector_store.rag_sdk_ingestion_impl import RagSdkIngestionService
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


def test_ingest_calls_processor_with_correct_args():
    processor = MagicMock()
    processor.ingest = AsyncMock()
    service = RagSdkIngestionService(processor)
    article = _make_article()

    service.ingest(article)

    processor.ingest.assert_called_once_with(
        full_text=article.content,
        metadata={
            "url": str(article.url),
            "title": article.title,
            "source": article.source,
        },
    )


def test_ingest_passes_full_content():
    processor = MagicMock()
    processor.ingest = AsyncMock()
    service = RagSdkIngestionService(processor)
    article = _make_article(content="Long detailed content of the research paper.")

    service.ingest(article)

    _, kwargs = processor.ingest.call_args
    assert kwargs["full_text"] == "Long detailed content of the research paper."


def test_ingest_includes_url_in_metadata():
    processor = MagicMock()
    processor.ingest = AsyncMock()
    service = RagSdkIngestionService(processor)
    article = _make_article()

    service.ingest(article)

    _, kwargs = processor.ingest.call_args
    assert kwargs["metadata"]["url"] == str(article.url)


def test_ingest_includes_title_in_metadata():
    processor = MagicMock()
    processor.ingest = AsyncMock()
    service = RagSdkIngestionService(processor)
    article = _make_article()

    service.ingest(article)

    _, kwargs = processor.ingest.call_args
    assert kwargs["metadata"]["title"] == article.title


def test_ingest_includes_source_in_metadata():
    processor = MagicMock()
    processor.ingest = AsyncMock()
    service = RagSdkIngestionService(processor)
    article = _make_article()

    service.ingest(article)

    _, kwargs = processor.ingest.call_args
    assert kwargs["metadata"]["source"] == article.source
