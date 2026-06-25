from unittest.mock import MagicMock
from uuid import uuid4

from src.modules.intelligence.application.use_cases.ingest_article_for_rag import IngestArticleForRagUseCase
from src.modules.intelligence.domain.services.rag_ingestion_service import RagIngestionService
from src.shared.domain.entities.article import Article


def _make_article(content="Abstract text.", metadata=None):
    return Article(
        id=uuid4(),
        url="https://arxiv.org/abs/2401.00001",
        url_hash="abc",
        source="arxiv",
        title="A Research Paper",
        content=content,
        metadata=metadata or {},
    )


def _make_use_case():
    service = MagicMock(spec=RagIngestionService)
    return IngestArticleForRagUseCase(service), service


def test_execute_passes_full_text_to_service():
    uc, service = _make_use_case()
    article = _make_article()
    full_text = "Complete PDF text including all sections."

    uc.execute(article, full_text)

    service.ingest.assert_called_once_with(article, full_text)


def test_execute_passes_article_to_service():
    uc, service = _make_use_case()
    article = _make_article()

    uc.execute(article, "some text")

    article_arg, _ = service.ingest.call_args[0]
    assert article_arg is article


def test_execute_fallback_uses_content_when_no_full_text():
    uc, service = _make_use_case()
    article = _make_article(content="Abstract only.")

    uc.execute(article, "")

    _, full_text = service.ingest.call_args[0]
    assert "Abstract only." in full_text
    assert "A Research Paper" in full_text


def test_execute_fallback_uses_content_when_whitespace_only_full_text():
    uc, service = _make_use_case()
    article = _make_article(content="Real abstract text.")

    uc.execute(article, "\n\n\n   \t")  # scanned PDF whitespace

    _, full_text = service.ingest.call_args[0]
    assert "Real abstract text." in full_text


def test_execute_fallback_includes_sections_from_metadata():
    uc, service = _make_use_case()
    article = _make_article(
        content="Abstract.",
        metadata={"sections": {"introduction": "Intro body.", "conclusion": "Conclude."}},
    )

    uc.execute(article)  # no full_text → fallback

    _, full_text = service.ingest.call_args[0]
    assert "## introduction" in full_text
    assert "Intro body." in full_text
    assert "## conclusion" in full_text


def test_execute_fallback_skips_empty_sections():
    uc, service = _make_use_case()
    article = _make_article(
        content="Abstract.",
        metadata={"sections": {"introduction": "Real content.", "empty": "   "}},
    )

    uc.execute(article)

    _, full_text = service.ingest.call_args[0]
    assert "## introduction" in full_text
    assert "## empty" not in full_text


def test_execute_skips_bot_detection_content():
    uc, service = _make_use_case()
    article = _make_article(content="some abstract")

    bot_text = "In order to continue, we need to verify that you're not a robot. This requires JavaScript."
    uc.execute(article, bot_text)

    service.ingest.assert_not_called()


def test_execute_skips_javascript_disabled_page():
    uc, service = _make_use_case()
    article = _make_article(content="some abstract")

    uc.execute(article, "Please enable JavaScript and then reload the page.")

    service.ingest.assert_not_called()


def test_execute_skips_empty_content_after_fallback():
    uc, service = _make_use_case()
    article = Article(
        id=uuid4(), url="https://example.com", url_hash="x",
        source="rss", title="", content="", metadata={},
    )

    uc.execute(article)

    service.ingest.assert_not_called()
