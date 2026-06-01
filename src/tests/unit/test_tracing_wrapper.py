"""
Unit tests for src/infrastructure/shared/observability/span_wrappers.py
"""
import pytest
from unittest.mock import MagicMock, call
from opentelemetry.trace import StatusCode
from src.infrastructure.shared.observability.span_wrappers import (
    with_span_deferred,
    with_article_pipeline_span,
)


def _make_mock_tracer():
    span = MagicMock()
    span.__enter__ = MagicMock(return_value=span)
    span.__exit__ = MagicMock(return_value=False)
    tracer = MagicMock()
    tracer.start_as_current_span.return_value = span
    return tracer, span


class FakeBus:
    def __init__(self):
        self.published = []

    def publish(self, event):
        self.published.append(event)


class TestWithSpanDeferred:
    def test_creates_span_with_correct_name(self):
        tracer, span = _make_mock_tracer()
        bus = FakeBus()
        handler = MagicMock(return_value="ok")

        wrapper = with_span_deferred("my.span", handler, bus, tracer)
        wrapper("evt")

        tracer.start_as_current_span.assert_called_once_with("my.span")

    def test_calls_handler_with_event(self):
        tracer, _ = _make_mock_tracer()
        bus = FakeBus()
        handler = MagicMock(return_value=None)

        wrapper = with_span_deferred("s", handler, bus, tracer)
        wrapper("my_event")

        handler.assert_called_once_with("my_event")

    def test_returns_handler_result(self):
        tracer, _ = _make_mock_tracer()
        bus = FakeBus()
        handler = MagicMock(return_value=42)

        result = with_span_deferred("s", handler, bus, tracer)("evt")

        assert result == 42

    def test_deferred_events_published_after_span_closes(self):
        tracer, span = _make_mock_tracer()
        bus = FakeBus()

        publish_calls_at_exit = []

        def capture_exit(*args, **kwargs):
            publish_calls_at_exit.append(list(bus.published))
            return False

        span.__exit__ = capture_exit

        def handler(event):
            bus.publish("downstream_event")

        wrapper = with_span_deferred("s", handler, bus, tracer)
        wrapper("evt")

        # At the moment __exit__ was called, no events should have been published yet
        assert publish_calls_at_exit[0] == []
        # After the wrapper completes, the deferred event is published
        assert bus.published == ["downstream_event"]

    def test_restores_original_publish_after_span(self):
        tracer, _ = _make_mock_tracer()
        bus = FakeBus()
        original_publish = bus.publish

        with_span_deferred("s", MagicMock(), bus, tracer)("evt")

        assert bus.publish == original_publish

    def test_restores_publish_even_on_exception(self):
        tracer, _ = _make_mock_tracer()
        bus = FakeBus()
        original_publish = bus.publish

        def failing(evt):
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            with_span_deferred("s", failing, bus, tracer)("evt")

        assert bus.publish == original_publish

    def test_records_exception_and_sets_error_status(self):
        tracer, span = _make_mock_tracer()
        bus = FakeBus()
        error = ValueError("test error")

        with pytest.raises(ValueError):
            with_span_deferred("s", MagicMock(side_effect=error), bus, tracer)("evt")

        span.record_exception.assert_called_once_with(error)
        span.set_status.assert_called_once()
        args = span.set_status.call_args[0]
        assert args[0] == StatusCode.ERROR

    def test_deferred_events_not_published_on_exception(self):
        tracer, _ = _make_mock_tracer()
        bus = FakeBus()

        def handler(event):
            bus.publish("should_not_appear")
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            with_span_deferred("s", handler, bus, tracer)("evt")

        assert bus.published == []


class TestWithArticlePipelineSpan:
    def _make_event(self):
        event = MagicMock()
        event.url = "https://arxiv.org/abs/123"
        event.source = "arxiv"
        return event

    def test_creates_pipeline_span_with_article_attrs(self):
        tracer, pipeline_span = _make_mock_tracer()
        bus = FakeBus()
        handler = MagicMock()

        # Inner span for scraped.handle needs its own mock
        scraped_span = MagicMock()
        scraped_span.__enter__ = MagicMock(return_value=scraped_span)
        scraped_span.__exit__ = MagicMock(return_value=False)
        tracer.start_as_current_span.side_effect = [pipeline_span, scraped_span]

        wrapper = with_article_pipeline_span(
            handler, bus, tracer, "article.pipeline", "article.scraped.handle"
        )
        wrapper(self._make_event())

        pipeline_span.set_attribute.assert_any_call("article.url", "https://arxiv.org/abs/123")
        pipeline_span.set_attribute.assert_any_call("article.source", "arxiv")

    def test_creates_scraped_handle_span_as_child(self):
        tracer, pipeline_span = _make_mock_tracer()
        bus = FakeBus()
        handler = MagicMock()

        scraped_span = MagicMock()
        scraped_span.__enter__ = MagicMock(return_value=scraped_span)
        scraped_span.__exit__ = MagicMock(return_value=False)
        tracer.start_as_current_span.side_effect = [pipeline_span, scraped_span]

        wrapper = with_article_pipeline_span(
            handler, bus, tracer, "article.pipeline", "article.scraped.handle"
        )
        wrapper(self._make_event())

        calls = [c[0][0] for c in tracer.start_as_current_span.call_args_list]
        assert calls[0] == "article.pipeline"
        assert calls[1] == "article.scraped.handle"