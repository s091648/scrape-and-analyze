import pytest
from opentelemetry import trace as otel_trace


def test_get_tracer_returns_tracer_instance():
    from src.observability.tracing import get_tracer
    tracer = get_tracer()
    assert tracer is not None
    assert isinstance(tracer, otel_trace.Tracer)


def test_shutdown_tracing_does_not_raise_when_no_provider(monkeypatch):
    import src.observability.tracing as tracing_module
    monkeypatch.setattr(tracing_module, "_provider", None)
    from src.observability.tracing import shutdown_tracing
    shutdown_tracing()  # must not raise


from unittest.mock import MagicMock, patch
from uuid import uuid4

from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def _make_test_provider() -> InMemorySpanExporter:
    """Install a fresh in-memory provider and return its exporter."""
    exporter = InMemorySpanExporter()
    provider = SDKTracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    # Directly set the module-level _tracer to a tracer from our in-memory provider
    import src.observability.tracing as tracing_mod
    tracing_mod._tracer = provider.get_tracer("scrape-analyzer")
    return exporter


def test_analyze_article_creates_span_with_llm_attributes():
    exporter = _make_test_provider()

    mock_session = MagicMock()
    mock_article = MagicMock()
    mock_article.id = uuid4()
    mock_article.url = "https://example.com/article"
    mock_article.source = "test_rss"
    mock_article.tags = []

    mock_result = MagicMock()
    mock_result.pain_points = "pain"
    mock_result.insights = "insights"
    mock_result.innovations = "innovations"
    mock_result.tag_groups = []
    mock_result.model_used = "gemini-pro"
    mock_result.input_tokens = 120
    mock_result.output_tokens = 60

    mock_analyzer = MagicMock()
    mock_analyzer.analyze.return_value = mock_result

    from src.main import analyze_article
    with patch("src.main.prepare_content_for_analysis", return_value="content"):
        result = analyze_article(
            mock_session, mock_article, mock_analyzer, "prompt", str(uuid4())
        )

    assert result is True
    finished = exporter.get_finished_spans()
    assert len(finished) == 1
    span = finished[0]
    assert span.name == "article.analyze"
    assert span.attributes["article.url"] == "https://example.com/article"
    assert span.attributes["article.source"] == "test_rss"
    assert span.attributes["article.id"] == str(mock_article.id)
    assert span.attributes["llm.model"] == "gemini-pro"
    assert span.attributes["llm.input_tokens"] == 120
    assert span.attributes["llm.output_tokens"] == 60


def test_analyze_article_span_has_error_status_when_result_is_none():
    from opentelemetry.trace import StatusCode

    exporter = _make_test_provider()

    mock_session = MagicMock()
    mock_article = MagicMock()
    mock_article.id = uuid4()
    mock_article.url = "https://example.com/fail"
    mock_article.source = "test_rss"

    mock_analyzer = MagicMock()
    mock_analyzer.analyze.return_value = None

    from src.main import analyze_article
    with patch("src.main.prepare_content_for_analysis", return_value="content"), \
         patch("src.main.record_failure"):
        result = analyze_article(
            mock_session, mock_article, mock_analyzer, "prompt", str(uuid4())
        )

    assert result is False
    span = exporter.get_finished_spans()[0]
    assert span.name == "article.analyze"
    assert span.status.status_code == StatusCode.ERROR
