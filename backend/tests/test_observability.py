"""Tests for backend/observability.py — Loki log shipping and OTel tracing setup.

backend/observability.py reads its GRAFANA_* config as names imported at module
load time from backend.config (not raw env vars), so tests patch those module
attributes directly rather than the environment — mirrors backend/tests/test_config.py's
approach of treating backend.config as the source of truth.
"""
import logging
import sys
from unittest.mock import MagicMock, patch


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
    from backend.observability import configure_logging
    original = _clear_root_handlers()
    try:
        with patch("backend.observability.GRAFANA_LOKI_URL", ""), \
             patch("backend.observability.GRAFANA_LOKI_USER", ""), \
             patch("backend.observability.GRAFANA_API_KEY", ""):
            configure_logging("local")
        root = logging.getLogger()
        has_stdout = any(
            isinstance(h, logging.StreamHandler) and h.stream is sys.stdout
            for h in root.handlers
        )
        assert has_stdout
    finally:
        _restore_root_handlers(original)


def test_loki_handler_not_attached_without_env():
    from backend.observability import configure_logging
    original = _clear_root_handlers()
    try:
        with patch("backend.observability.GRAFANA_LOKI_URL", ""), \
             patch("backend.observability.GRAFANA_LOKI_USER", ""), \
             patch("backend.observability.GRAFANA_API_KEY", ""):
            configure_logging("local")
        handler_types = [type(h).__name__ for h in logging.getLogger().handlers]
        assert "LokiHandler" not in handler_types
    finally:
        _restore_root_handlers(original)


def test_loki_handler_attached_with_env():
    from backend.observability import configure_logging
    original = _clear_root_handlers()
    mock_loki_handler = MagicMock()
    mock_loki_module = MagicMock()
    mock_loki_module.LokiHandler.return_value = mock_loki_handler
    try:
        with patch("backend.observability.GRAFANA_LOKI_URL", "https://loki.example.com"), \
             patch("backend.observability.GRAFANA_LOKI_USER", "loki-user"), \
             patch("backend.observability.GRAFANA_API_KEY", "api-key"), \
             patch.dict("sys.modules", {"logging_loki": mock_loki_module}):
            configure_logging("production")
        assert mock_loki_handler in logging.getLogger().handlers
        mock_loki_module.LokiHandler.assert_called_once()
        _, kwargs = mock_loki_module.LokiHandler.call_args
        assert kwargs["url"] == "https://loki.example.com/push"
        assert kwargs["auth"] == ("loki-user", "api-key")
    finally:
        _restore_root_handlers(original)


def test_loki_setup_failure_is_swallowed():
    """If LokiHandler() raises, configure_logging() does not raise and stdout still works."""
    from backend.observability import configure_logging
    original = _clear_root_handlers()
    mock_loki_module = MagicMock()
    mock_loki_module.LokiHandler.side_effect = Exception("Connection refused")
    try:
        with patch("backend.observability.GRAFANA_LOKI_URL", "https://loki.example.com"), \
             patch("backend.observability.GRAFANA_LOKI_USER", "loki-user"), \
             patch("backend.observability.GRAFANA_API_KEY", "api-key"), \
             patch.dict("sys.modules", {"logging_loki": mock_loki_module}):
            configure_logging("local")  # must not raise
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
    from backend.observability import setup_tracing
    with patch("backend.observability.GRAFANA_OTLP_USER", ""), \
         patch("backend.observability.GRAFANA_API_KEY", ""), \
         patch("backend.observability.GRAFANA_OTLP_ENDPOINT", ""):
        assert setup_tracing("local") is None


def test_setup_tracing_returns_provider_with_env():
    from backend.observability import setup_tracing
    with patch("backend.observability.GRAFANA_OTLP_USER", "otlp-user"), \
         patch("backend.observability.GRAFANA_API_KEY", "api-key"), \
         patch("backend.observability.GRAFANA_OTLP_ENDPOINT", "https://otlp.example.com"):
        provider = setup_tracing("production")
    try:
        from opentelemetry.sdk.trace import TracerProvider
        assert isinstance(provider, TracerProvider)
    finally:
        if provider:
            provider.shutdown()


def test_setup_tracing_failure_is_swallowed():
    """If the OTLP exporter setup raises, setup_tracing() returns None instead of raising."""
    from backend.observability import setup_tracing
    with patch("backend.observability.GRAFANA_OTLP_USER", "otlp-user"), \
         patch("backend.observability.GRAFANA_API_KEY", "api-key"), \
         patch("backend.observability.GRAFANA_OTLP_ENDPOINT", "https://otlp.example.com"), \
         patch(
             "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
             side_effect=Exception("boom"),
         ):
        assert setup_tracing("local") is None


# ---------------------------------------------------------------------------
# _add_otel_context structlog processor
# ---------------------------------------------------------------------------

def test_add_otel_context_injects_trace_and_span_id():
    from backend.observability import _add_otel_context
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry import trace

    provider = TracerProvider()
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("test.span"):
        event_dict = _add_otel_context(None, "info", {"event": "hi"})
    assert "trace_id" in event_dict
    assert "span_id" in event_dict
    assert len(event_dict["trace_id"]) == 32
    assert len(event_dict["span_id"]) == 16


def test_add_otel_context_noop_without_active_span():
    from backend.observability import _add_otel_context
    event_dict = _add_otel_context(None, "info", {"event": "hi"})
    assert "trace_id" not in event_dict
    assert "span_id" not in event_dict
