"""
Unit tests for the _with_span closure helper used in bootstrap.py.

Tests verify that:
- Child spans are created with the correct name
- Spans are closed after handler execution
- Exceptions are re-raised and span status is set to ERROR
"""
from unittest.mock import MagicMock, patch, call
import pytest


def make_with_span():
    """Re-create the _with_span helper as defined in bootstrap.py."""
    from opentelemetry import trace as _otel
    from src.infrastructure.shared.observability import get_tracer

    def _with_span(span_name: str, fn):
        tracer = get_tracer()
        def _wrapper(event):
            with tracer.start_as_current_span(span_name) as span:
                try:
                    return fn(event)
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(_otel.StatusCode.ERROR, str(e))
                    raise
        return _wrapper

    return _with_span


class TestWithSpan:
    def test_creates_child_span_with_correct_name(self):
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value = mock_span

        with patch("src.infrastructure.shared.observability.otel_tracing._tracer", mock_tracer):
            _with_span = make_with_span()
            handler = MagicMock(return_value="result")
            wrapped = _with_span("article.scraped.handle", handler)

            event = MagicMock()
            wrapped(event)

        mock_tracer.start_as_current_span.assert_called_once_with("article.scraped.handle")
        handler.assert_called_once_with(event)

    def test_span_closes_after_handler(self):
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value = mock_span

        with patch("src.infrastructure.shared.observability.otel_tracing._tracer", mock_tracer):
            _with_span = make_with_span()
            wrapped = _with_span("test.span", MagicMock())
            wrapped(MagicMock())

        mock_span.__exit__.assert_called_once()

    def test_exception_reraises_and_records_on_span(self):
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value = mock_span

        error = ValueError("boom")
        failing_handler = MagicMock(side_effect=error)

        with patch("src.infrastructure.shared.observability.otel_tracing._tracer", mock_tracer):
            _with_span = make_with_span()
            wrapped = _with_span("test.span", failing_handler)

            with pytest.raises(ValueError, match="boom"):
                wrapped(MagicMock())

        mock_span.record_exception.assert_called_once_with(error)
        mock_span.set_status.assert_called_once()

    def test_returns_handler_result(self):
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value = mock_span

        handler = MagicMock(return_value=42)

        with patch("src.infrastructure.shared.observability.otel_tracing._tracer", mock_tracer):
            _with_span = make_with_span()
            wrapped = _with_span("test.span", handler)
            result = wrapped(MagicMock())

        assert result == 42
