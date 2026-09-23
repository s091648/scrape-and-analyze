"""Tests for backend/observability.py — Loki log shipping and OTel tracing setup.

backend/observability.py reads its GRAFANA_* config as names imported at module
load time from backend.config (not raw env vars), so tests patch those module
attributes directly rather than the environment — mirrors backend/tests/test_config.py's
approach of treating backend.config as the source of truth.
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
        assert "LokiQueueHandler" not in handler_types
    finally:
        _restore_root_handlers(original)


def test_loki_handler_attached_with_env():
    """Uses LokiQueueHandler (queue + background thread), not the plain LokiHandler — the
    plain handler does a synchronous requests.post() to Grafana Cloud on every logger.info()
    call, which measurably blocked every request (see backend/observability.py comment)."""
    from backend.observability import configure_logging
    original = _clear_root_handlers()
    mock_loki_handler = MagicMock()
    mock_loki_module = MagicMock()
    mock_loki_module.LokiQueueHandler.return_value = mock_loki_handler
    try:
        with patch("backend.observability.GRAFANA_LOKI_URL", "https://loki.example.com"), \
             patch("backend.observability.GRAFANA_LOKI_USER", "loki-user"), \
             patch("backend.observability.GRAFANA_API_KEY", "api-key"), \
             patch.dict("sys.modules", {"logging_loki": mock_loki_module}):
            configure_logging("production")
        assert mock_loki_handler in logging.getLogger().handlers
        mock_loki_module.LokiQueueHandler.assert_called_once()
        _, kwargs = mock_loki_module.LokiQueueHandler.call_args
        assert kwargs["url"] == "https://loki.example.com/push"
        assert kwargs["auth"] == ("loki-user", "api-key")
    finally:
        _restore_root_handlers(original)


def test_httpx_and_httpcore_loggers_raised_to_warning():
    """httpx logs an INFO line per outbound request (e.g. proxying Grafana queries);
    configure_logging() must silence that noise so it doesn't bury real app logs
    in Loki, without touching its own WARNING+ output."""
    from backend.observability import configure_logging
    original = _clear_root_handlers()
    try:
        with patch("backend.observability.GRAFANA_LOKI_URL", ""), \
             patch("backend.observability.GRAFANA_LOKI_USER", ""), \
             patch("backend.observability.GRAFANA_API_KEY", ""):
            configure_logging("local")
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING
    finally:
        _restore_root_handlers(original)


def test_loki_setup_failure_is_swallowed():
    """If LokiQueueHandler() raises, configure_logging() does not raise and stdout still works."""
    from backend.observability import configure_logging
    original = _clear_root_handlers()
    mock_loki_module = MagicMock()
    mock_loki_module.LokiQueueHandler.side_effect = Exception("Connection refused")
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


# ---------------------------------------------------------------------------
# setup_profiling
# ---------------------------------------------------------------------------

def test_setup_profiling_skipped_without_env():
    from backend.observability import setup_profiling
    with patch("backend.observability.GRAFANA_PROFILES_URL", ""), \
         patch("backend.observability.GRAFANA_PROFILES_USER", ""), \
         patch("backend.observability.GRAFANA_API_KEY", ""):
        assert setup_profiling("local") is None


def test_setup_profiling_configures_pyroscope_with_env():
    from backend.observability import setup_profiling
    mock_pyroscope = MagicMock()
    with patch("backend.observability.GRAFANA_PROFILES_URL", "https://profiles.example.com"), \
         patch("backend.observability.GRAFANA_PROFILES_USER", "profiles-user"), \
         patch("backend.observability.GRAFANA_API_KEY", "api-key"), \
         patch.dict("sys.modules", {"pyroscope": mock_pyroscope}):
        setup_profiling("production")

    mock_pyroscope.configure.assert_called_once()
    _, kwargs = mock_pyroscope.configure.call_args
    assert kwargs["server_address"] == "https://profiles.example.com"
    assert kwargs["basic_auth_username"] == "profiles-user"
    assert kwargs["basic_auth_password"] == "api-key"
    assert kwargs["tags"] == {"env": "production"}


def test_setup_profiling_failure_is_swallowed():
    """If pyroscope.configure() raises, setup_profiling() must not raise."""
    from backend.observability import setup_profiling
    mock_pyroscope = MagicMock()
    mock_pyroscope.configure.side_effect = Exception("connection refused")
    with patch("backend.observability.GRAFANA_PROFILES_URL", "https://profiles.example.com"), \
         patch("backend.observability.GRAFANA_PROFILES_USER", "profiles-user"), \
         patch("backend.observability.GRAFANA_API_KEY", "api-key"), \
         patch.dict("sys.modules", {"pyroscope": mock_pyroscope}):
        setup_profiling("local")  # must not raise


def test_setup_profiling_leaves_profiling_disabled_on_failure():
    """_profiling_enabled must stay False when pyroscope.configure() raised — otherwise
    to_thread_profiled() would try to tag threads against a profiler that never actually
    started."""
    from backend import observability
    mock_pyroscope = MagicMock()
    mock_pyroscope.configure.side_effect = Exception("connection refused")
    with patch.object(observability, "_profiling_enabled", False), \
         patch("backend.observability.GRAFANA_PROFILES_URL", "https://profiles.example.com"), \
         patch("backend.observability.GRAFANA_PROFILES_USER", "profiles-user"), \
         patch("backend.observability.GRAFANA_API_KEY", "api-key"), \
         patch.dict("sys.modules", {"pyroscope": mock_pyroscope}):
        observability.setup_profiling("local")
        assert observability._profiling_enabled is False


def test_setup_profiling_enables_profiling_on_success():
    from backend import observability
    mock_pyroscope = MagicMock()
    with patch.object(observability, "_profiling_enabled", False), \
         patch("backend.observability.GRAFANA_PROFILES_URL", "https://profiles.example.com"), \
         patch("backend.observability.GRAFANA_PROFILES_USER", "profiles-user"), \
         patch("backend.observability.GRAFANA_API_KEY", "api-key"), \
         patch.dict("sys.modules", {"pyroscope": mock_pyroscope}):
        observability.setup_profiling("production")
        assert observability._profiling_enabled is True


# ---------------------------------------------------------------------------
# _current_span_tags / to_thread_profiled (fix/profiler_imprv — trace-to-profile
# correlation: tag CPU samples with the currently active span_id when a sync/blocking call
# is dispatched via to_thread_profiled, so GET /grafana/profile?span_id=... can later scope
# the flamebearer to exactly that span instead of the whole padded request window).
# ---------------------------------------------------------------------------

def test_current_span_tags_empty_without_active_span():
    from backend.observability import _current_span_tags
    assert _current_span_tags() == {}


def test_current_span_tags_returns_span_id_with_active_span():
    from backend.observability import _current_span_tags
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("test.span"):
        tags = _current_span_tags()
    assert list(tags.keys()) == ["span_id"]
    assert len(tags["span_id"]) == 16


@pytest.mark.asyncio
async def test_to_thread_profiled_runs_func_when_profiling_disabled():
    from backend import observability
    with patch.object(observability, "_profiling_enabled", False):
        result = await observability.to_thread_profiled(lambda x: x * 2, 21)
    assert result == 42


@pytest.mark.asyncio
async def test_to_thread_profiled_runs_func_without_active_span():
    """Profiling enabled but no OTel span active (e.g. a background job, not a request) —
    still just a plain to_thread(), no tagging attempted."""
    from backend import observability
    with patch.object(observability, "_profiling_enabled", True):
        result = await observability.to_thread_profiled(lambda x: x + 1, 41)
    assert result == 42


@pytest.mark.asyncio
async def test_to_thread_profiled_tags_thread_with_current_span_id():
    from backend import observability
    from opentelemetry.sdk.trace import TracerProvider

    mock_pyroscope = MagicMock()
    provider = TracerProvider()
    tracer = provider.get_tracer("test")

    with patch.object(observability, "_profiling_enabled", True), \
         patch.dict("sys.modules", {"pyroscope": mock_pyroscope}):
        with tracer.start_as_current_span("test.span") as span:
            span_id = format(span.get_span_context().span_id, "016x")
            result = await observability.to_thread_profiled(lambda x: x * 2, 5)

    assert result == 10
    mock_pyroscope.tag_wrapper.assert_called_once_with({"span_id": span_id})
    mock_pyroscope.tag_wrapper.return_value.__enter__.assert_called_once()
    mock_pyroscope.tag_wrapper.return_value.__exit__.assert_called_once()


@pytest.mark.asyncio
async def test_to_thread_profiled_still_runs_func_when_tagging_fails():
    """A pyroscope native-lib hiccup while tagging must not prevent func from running —
    profiling is best-effort everywhere else in this module, this helper is no exception."""
    from backend import observability
    from opentelemetry.sdk.trace import TracerProvider

    mock_pyroscope = MagicMock()
    mock_pyroscope.tag_wrapper.side_effect = Exception("native lib error")
    provider = TracerProvider()
    tracer = provider.get_tracer("test")

    with patch.object(observability, "_profiling_enabled", True), \
         patch.dict("sys.modules", {"pyroscope": mock_pyroscope}):
        with tracer.start_as_current_span("test.span"):
            result = await observability.to_thread_profiled(lambda x: x * 2, 5)

    assert result == 10


@pytest.mark.asyncio
async def test_to_thread_profiled_propagates_func_exception():
    from backend import observability

    def _boom():
        raise ValueError("boom")

    with patch.object(observability, "_profiling_enabled", False):
        with pytest.raises(ValueError, match="boom"):
            await observability.to_thread_profiled(_boom)
