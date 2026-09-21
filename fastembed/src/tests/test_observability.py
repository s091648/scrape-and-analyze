"""Tests for fastembed_service/observability.py — JSON stdout logging, optional
Loki shipping, OTel tracing setup, and the traceback-chain filtering used by the
JSON formatter when a log record carries exc_info.

Unlike backend/observability.py (structlog-based), this module builds on plain
stdlib logging: configure_logging()/setup_tracing() take their config as
explicit arguments (not module-level imports), so tests pass values directly
rather than patching module attributes.
"""
import logging
import sys
from unittest.mock import MagicMock, patch

import pytest


def _clear_root_handlers():
    root = logging.getLogger()
    handlers = root.handlers[:]
    for h in handlers:
        root.removeHandler(h)
    return handlers


def _restore_root_handlers(handlers):
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    for h in handlers:
        root.addHandler(h)


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------

def test_stdout_handler_always_attached():
    from fastembed_service.observability import configure_logging
    original = _clear_root_handlers()
    try:
        configure_logging(service="fastembed")
        root = logging.getLogger()
        has_stdout = any(
            isinstance(h, logging.StreamHandler) and h.stream is sys.stdout
            for h in root.handlers
        )
        assert has_stdout
        assert root.level == logging.INFO
    finally:
        _restore_root_handlers(original)


def test_loki_handler_not_attached_without_env():
    from fastembed_service.observability import configure_logging
    original = _clear_root_handlers()
    try:
        configure_logging(service="fastembed")
        assert len(logging.getLogger().handlers) == 1
    finally:
        _restore_root_handlers(original)


def test_loki_handler_attached_with_env():
    from fastembed_service.observability import configure_logging
    original = _clear_root_handlers()
    mock_loki_handler = MagicMock()
    mock_loki_module = MagicMock()
    mock_loki_module.LokiHandler.return_value = mock_loki_handler
    try:
        with patch.dict("sys.modules", {"logging_loki": mock_loki_module}):
            configure_logging(
                service="fastembed",
                loki_url="https://loki.example.com",
                loki_user="loki-user",
                loki_api_key="api-key",
                app_env="production",
            )
        assert mock_loki_handler in logging.getLogger().handlers
        mock_loki_module.LokiHandler.assert_called_once()
        _, kwargs = mock_loki_module.LokiHandler.call_args
        assert kwargs["url"] == "https://loki.example.com/push"
        assert kwargs["auth"] == ("loki-user", "api-key")
        assert kwargs["tags"] == {"app": "fastembed", "env": "production"}
    finally:
        _restore_root_handlers(original)


def test_loki_handler_not_attached_when_only_some_env_set():
    from fastembed_service.observability import configure_logging
    original = _clear_root_handlers()
    try:
        configure_logging(service="fastembed", loki_url="https://loki.example.com")
        assert len(logging.getLogger().handlers) == 1
    finally:
        _restore_root_handlers(original)


def test_loki_setup_failure_is_swallowed():
    """If LokiHandler() raises, configure_logging() does not raise and stdout still works."""
    from fastembed_service.observability import configure_logging
    original = _clear_root_handlers()
    mock_loki_module = MagicMock()
    mock_loki_module.LokiHandler.side_effect = Exception("Connection refused")
    try:
        with patch.dict("sys.modules", {"logging_loki": mock_loki_module}):
            configure_logging(
                service="fastembed",
                loki_url="https://loki.example.com",
                loki_user="loki-user",
                loki_api_key="api-key",
            )  # must not raise
        has_stdout = any(
            isinstance(h, logging.StreamHandler) and h.stream is sys.stdout
            for h in logging.getLogger().handlers
        )
        assert has_stdout
    finally:
        _restore_root_handlers(original)


# ---------------------------------------------------------------------------
# setup_tracing
# ---------------------------------------------------------------------------

def test_setup_tracing_returns_none_without_env():
    from fastembed_service.observability import setup_tracing
    assert setup_tracing("local", "", "", "") is None


def test_setup_tracing_returns_none_when_only_some_env_set():
    from fastembed_service.observability import setup_tracing
    assert setup_tracing("local", "https://otlp.example.com", "", "api-key") is None


def test_setup_tracing_returns_provider_with_env():
    from fastembed_service.observability import setup_tracing
    provider = setup_tracing("production", "https://otlp.example.com", "otlp-user", "api-key")
    try:
        from opentelemetry.sdk.trace import TracerProvider
        assert isinstance(provider, TracerProvider)
    finally:
        if provider:
            provider.shutdown()


def test_setup_tracing_failure_is_swallowed():
    """If the OTLP exporter setup raises, setup_tracing() returns None instead of raising."""
    from fastembed_service.observability import setup_tracing
    with patch(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
        side_effect=Exception("boom"),
    ):
        assert setup_tracing("local", "https://otlp.example.com", "otlp-user", "api-key") is None


# ---------------------------------------------------------------------------
# _add_otel_context
# ---------------------------------------------------------------------------

def _make_record(**extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hi", args=(), exc_info=None,
    )
    for k, v in extra.items():
        setattr(record, k, v)
    return record


def test_add_otel_context_injects_trace_and_span_id():
    from fastembed_service.observability import _add_otel_context
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    tracer = provider.get_tracer("test")
    record = _make_record()
    with tracer.start_as_current_span("test.span"):
        result = _add_otel_context(record)
    assert result is True
    assert len(record.trace_id) == 32
    assert len(record.span_id) == 16


def test_add_otel_context_noop_without_active_span():
    from fastembed_service.observability import _add_otel_context
    record = _make_record()
    assert _add_otel_context(record) is True
    assert not hasattr(record, "trace_id")
    assert not hasattr(record, "span_id")


def test_add_otel_context_swallows_exceptions():
    from fastembed_service.observability import _add_otel_context
    record = _make_record()
    with patch("opentelemetry.trace.get_current_span", side_effect=Exception("boom")):
        assert _add_otel_context(record) is True


# ---------------------------------------------------------------------------
# _JsonFormatter
# ---------------------------------------------------------------------------

def test_json_formatter_includes_standard_fields():
    import json
    from fastembed_service.observability import _JsonFormatter

    fmt = _JsonFormatter("fastembed")
    record = _make_record()
    payload = json.loads(fmt.format(record))
    assert payload["event"] == "hi"
    assert payload["level"] == "info"
    assert payload["logger"] == "test"
    assert payload["service"] == "fastembed"
    assert "timestamp" in payload


def test_json_formatter_includes_extra_fields_not_double_underscore_prefixed():
    import json
    from fastembed_service.observability import _JsonFormatter

    fmt = _JsonFormatter("fastembed")
    record = _make_record(text_count=3, _internal="hidden")
    payload = json.loads(fmt.format(record))
    assert payload["text_count"] == 3
    assert "_internal" not in payload


def test_json_formatter_includes_exception_when_exc_info_present():
    import json
    from fastembed_service.observability import _JsonFormatter

    fmt = _JsonFormatter("fastembed")
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="failed", args=(), exc_info=sys.exc_info(),
        )
    payload = json.loads(fmt.format(record))
    assert "ValueError: boom" in payload["exception"]


# ---------------------------------------------------------------------------
# _format_single / _format_filtered_exception — in-app frame filtering across
# the __cause__/__context__ chain.
# ---------------------------------------------------------------------------

def _raise_and_capture():
    """Raises inside this test file (an "in-app" frame under _IN_APP_PREFIXES
    only if this file lived under fastembed_service/ — it doesn't, so every
    frame here is "outside", exercising the all-frames-omitted fallback)."""
    try:
        raise ValueError("boom")
    except ValueError:
        return sys.exc_info()


def test_format_single_falls_back_to_all_frames_when_none_are_in_app():
    from fastembed_service.observability import _format_single
    exc_type, exc, tb = _raise_and_capture()
    text = _format_single(exc_type, exc, tb)
    assert "ValueError: boom" in text
    assert "Traceback (most recent call last):" in text


def test_format_single_keeps_only_in_app_frames_and_reports_omitted_count():
    """Mocks traceback.extract_tb directly (rather than building a real multi-file
    traceback) to control exactly which frames look "in-app" vs. "foreign"."""
    import traceback as tb_module
    from fastembed_service import observability

    frames = [
        tb_module.FrameSummary("fastembed_service/routers/embed.py", 10, "embed"),
        tb_module.FrameSummary("/site-packages/fastapi/routing.py", 200, "run_endpoint_function"),
        tb_module.FrameSummary("/site-packages/starlette/routing.py", 50, "app"),
    ]
    with patch.object(observability, "_IN_APP_PREFIXES", ["fastembed_service"]), \
         patch("traceback.extract_tb", return_value=frames):
        text = observability._format_single(ValueError, ValueError("boom"), None)
    assert "2 frame(s) outside this project/whitelisted packages omitted" in text
    assert "embed" in text
    assert "run_endpoint_function" not in text


def test_format_filtered_exception_marks_direct_cause_chain():
    from fastembed_service.observability import _format_filtered_exception
    try:
        try:
            raise ValueError("inner")
        except ValueError as inner:
            raise RuntimeError("outer") from inner
    except RuntimeError:
        exc_info = sys.exc_info()
    text = _format_filtered_exception(exc_info)
    assert "ValueError: inner" in text
    assert "RuntimeError: outer" in text
    assert "was the direct cause of the following exception" in text


def test_format_filtered_exception_marks_implicit_context_chain():
    from fastembed_service.observability import _format_filtered_exception
    try:
        try:
            raise ValueError("inner")
        except ValueError:
            raise RuntimeError("outer")
    except RuntimeError:
        exc_info = sys.exc_info()
    text = _format_filtered_exception(exc_info)
    assert "During handling of the above exception, another exception occurred" in text


def test_format_filtered_exception_single_exception_no_chain_connector():
    from fastembed_service.observability import _format_filtered_exception
    try:
        raise ValueError("solo")
    except ValueError:
        exc_info = sys.exc_info()
    text = _format_filtered_exception(exc_info)
    assert "ValueError: solo" in text
    assert "direct cause" not in text
    assert "During handling" not in text
