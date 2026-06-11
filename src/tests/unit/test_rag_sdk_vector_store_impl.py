from unittest.mock import MagicMock
from uuid import uuid4

from src.infrastructure.vector_store.rag_sdk_vector_store_impl import RagSdkVectorStoreService
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
    service = RagSdkVectorStoreService(processor)
    article = _make_article()

    service.ingest(article)

    processor.ingest.assert_called_once_with(
        full_text=article.content,
        metadata={
            "article_id": str(article.id),
            "source_url": str(article.url),
        },
    )


def test_ingest_passes_full_content():
    processor = MagicMock()
    service = RagSdkVectorStoreService(processor)
    article = _make_article(content="Long detailed content of the research paper.")

    service.ingest(article)

    _, kwargs = processor.ingest.call_args
    assert kwargs["full_text"] == "Long detailed content of the research paper."


def test_ingest_includes_article_id_in_metadata():
    processor = MagicMock()
    service = RagSdkVectorStoreService(processor)
    article = _make_article()

    service.ingest(article)

    _, kwargs = processor.ingest.call_args
    assert kwargs["metadata"]["article_id"] == str(article.id)


def test_ingest_includes_source_url_in_metadata():
    processor = MagicMock()
    service = RagSdkVectorStoreService(processor)
    article = _make_article()

    service.ingest(article)

    _, kwargs = processor.ingest.call_args
    assert kwargs["metadata"]["source_url"] == str(article.url)
