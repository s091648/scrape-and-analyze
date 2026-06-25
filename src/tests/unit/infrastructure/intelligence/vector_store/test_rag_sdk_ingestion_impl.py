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


def test_ingest_calls_processor_with_provided_full_text():
    processor = MagicMock()
    processor.ingest = AsyncMock()
    service = RagSdkIngestionService(processor)
    article = _make_article()
    full_text = "Title\n\nAbstract text\n\n## Introduction\nIntro body"

    service.ingest(article, full_text)

    processor.ingest.assert_called_once_with(
        full_text=full_text,
        articles_column_values={
            "url": str(article.url),
            "title": article.title,
            "source": article.source,
            "public_article_id": str(article.id),
            "topic_id": None,
        },
    )


def test_ingest_uses_provided_full_text_not_article_content():
    processor = MagicMock()
    processor.ingest = AsyncMock()
    service = RagSdkIngestionService(processor)
    article = _make_article(content="Short abstract only.")
    full_text = "Short abstract only.\n\n## Introduction\nFull PDF section text."

    service.ingest(article, full_text)

    _, kwargs = processor.ingest.call_args
    assert kwargs["full_text"] == full_text
    assert "Full PDF section text." in kwargs["full_text"]


def test_ingest_includes_url_in_articles_column_values():
    processor = MagicMock()
    processor.ingest = AsyncMock()
    service = RagSdkIngestionService(processor)
    article = _make_article()

    service.ingest(article, "some text")

    _, kwargs = processor.ingest.call_args
    assert kwargs["articles_column_values"]["url"] == str(article.url)


def test_ingest_includes_title_in_articles_column_values():
    processor = MagicMock()
    processor.ingest = AsyncMock()
    service = RagSdkIngestionService(processor)
    article = _make_article()

    service.ingest(article, "some text")

    _, kwargs = processor.ingest.call_args
    assert kwargs["articles_column_values"]["title"] == article.title


def test_ingest_includes_source_in_articles_column_values():
    processor = MagicMock()
    processor.ingest = AsyncMock()
    service = RagSdkIngestionService(processor)
    article = _make_article()

    service.ingest(article, "some text")

    _, kwargs = processor.ingest.call_args
    assert kwargs["articles_column_values"]["source"] == article.source


def test_ingest_includes_public_article_id_in_articles_column_values():
    processor = MagicMock()
    processor.ingest = AsyncMock()
    service = RagSdkIngestionService(processor)
    article = _make_article()

    service.ingest(article, "some text")

    _, kwargs = processor.ingest.call_args
    assert kwargs["articles_column_values"]["public_article_id"] == str(article.id)
