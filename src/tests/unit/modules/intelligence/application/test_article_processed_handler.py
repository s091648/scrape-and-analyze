"""
Unit tests for ArticleProcessedHandler — covers span attributes written to
the current OTel span after LLM analysis completes.
"""
import uuid
from unittest.mock import MagicMock, patch

from src.modules.intelligence.application.events import (
    AnalysisCompletedEvent,
    AnalysisFailedEvent,
)
from src.modules.intelligence.application.use_cases.analysis_result import AnalysisResult
from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata
from src.modules.intelligence.domain.entities import Analysis
from src.shared.application.events import ArticleProcessedEvent
from src.shared.domain.entities import Article


def _make_article() -> Article:
    return Article(
        url="https://example.com/article",
        url_hash="a" * 64,
        source="rss",
        title="Test Article",
        content="Test content",
    )


def _make_analysis(article_id: uuid.UUID) -> Analysis:
    content = MagicMock(spec=AnalysisContent)
    content.tag_groups = []
    metadata = AnalysisMetadata(
        model_used="gemini-flash",
        input_tokens=1200,
        output_tokens=300,
    )
    analysis = Analysis(article_id=article_id, analysis_content=content, analysis_metadata=metadata)
    return analysis


def _make_handler():
    from src.modules.intelligence.application.event_handlers.article_processed_handler import (
        ArticleProcessedHandler,
    )
    use_case = MagicMock()
    event_bus = MagicMock()
    return ArticleProcessedHandler(use_case=use_case, event_bus=event_bus), use_case, event_bus


# ── Existing behaviour (preserved) ───────────────────────────────────────────

def test_publishes_analysis_completed_on_success():
    handler, use_case, event_bus = _make_handler()
    article = _make_article()
    analysis = _make_analysis(article.id)
    use_case.execute.return_value = AnalysisResult(
        success=True, article_id=article.id, article_url=article.url, analysis=analysis
    )
    handler.handle(ArticleProcessedEvent(article=article))
    event_bus.publish.assert_called_once()
    published = event_bus.publish.call_args[0][0]
    assert isinstance(published, AnalysisCompletedEvent)


def test_publishes_analysis_failed_on_failure():
    handler, use_case, event_bus = _make_handler()
    article = _make_article()
    use_case.execute.return_value = AnalysisResult(
        success=False, article_id=article.id, article_url=article.url,
        exception_type="LLMAnalysisError", exception_message="all providers failed",
    )
    handler.handle(ArticleProcessedEvent(article=article))
    published = event_bus.publish.call_args[0][0]
    assert isinstance(published, AnalysisFailedEvent)


# ── Span attribute tests ──────────────────────────────────────────────────────

def test_span_records_article_id_and_source():
    handler, use_case, event_bus = _make_handler()
    article = _make_article()
    analysis = _make_analysis(article.id)
    use_case.execute.return_value = AnalysisResult(
        success=True, article_id=article.id, article_url=article.url, analysis=analysis
    )
    mock_span = MagicMock()

    with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
        handler.handle(ArticleProcessedEvent(article=article))

    mock_span.set_attribute.assert_any_call("article.id", str(article.id))
    mock_span.set_attribute.assert_any_call("article.source", "rss")


def test_span_records_llm_metadata_on_success():
    handler, use_case, event_bus = _make_handler()
    article = _make_article()
    analysis = _make_analysis(article.id)
    use_case.execute.return_value = AnalysisResult(
        success=True, article_id=article.id, article_url=article.url, analysis=analysis
    )
    mock_span = MagicMock()

    with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
        handler.handle(ArticleProcessedEvent(article=article))

    mock_span.set_attribute.assert_any_call("llm.model", "gemini-flash")
    mock_span.set_attribute.assert_any_call("llm.input_tokens", 1200)
    mock_span.set_attribute.assert_any_call("llm.output_tokens", 300)
    mock_span.set_attribute.assert_any_call("analysis.id", str(analysis.id))
    mock_span.set_attribute.assert_any_call("analysis.success", True)


def test_span_records_error_type_on_failure():
    handler, use_case, event_bus = _make_handler()
    article = _make_article()
    use_case.execute.return_value = AnalysisResult(
        success=False, article_id=article.id, article_url=article.url,
        exception_type="LLMAnalysisError", exception_message="all providers failed",
    )
    mock_span = MagicMock()

    with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
        handler.handle(ArticleProcessedEvent(article=article))

    mock_span.set_attribute.assert_any_call("analysis.success", False)
    mock_span.set_attribute.assert_any_call("analysis.error_type", "LLMAnalysisError")
