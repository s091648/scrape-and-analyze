"""Tests for the scraper's own continuous CPU profiling (fix/profiler_imprv) — mirrors
backend/tests/test_observability.py's setup_profiling/to_thread_profiled coverage, adapted
for run_tagged_for_profiling()'s direct-call (no asyncio.to_thread bridging) shape."""
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# setup_profiling
# ---------------------------------------------------------------------------

def test_setup_profiling_skipped_without_env():
    from src.infrastructure.shared.observability import pyroscope_profiling as pp
    with patch.object(pp, "GRAFANA_PROFILES_URL", None), \
         patch.object(pp, "GRAFANA_PROFILES_USER", None), \
         patch.object(pp, "GRAFANA_API_KEY", None):
        assert pp.setup_profiling("local") is None


def test_setup_profiling_configures_pyroscope_with_env():
    from src.infrastructure.shared.observability import pyroscope_profiling as pp
    mock_pyroscope = MagicMock()
    with patch.object(pp, "GRAFANA_PROFILES_URL", "https://profiles.example.com"), \
         patch.object(pp, "GRAFANA_PROFILES_USER", "profiles-user"), \
         patch.object(pp, "GRAFANA_API_KEY", "api-key"), \
         patch.dict("sys.modules", {"pyroscope": mock_pyroscope}):
        pp.setup_profiling("production")

    mock_pyroscope.configure.assert_called_once()
    _, kwargs = mock_pyroscope.configure.call_args
    assert kwargs["application_name"] == "scrape-analyzer"
    assert kwargs["server_address"] == "https://profiles.example.com"
    assert kwargs["basic_auth_username"] == "profiles-user"
    assert kwargs["basic_auth_password"] == "api-key"
    assert kwargs["tags"] == {"env": "production"}


def test_setup_profiling_failure_is_swallowed():
    """If pyroscope.configure() raises, setup_profiling() must not raise."""
    from src.infrastructure.shared.observability import pyroscope_profiling as pp
    mock_pyroscope = MagicMock()
    mock_pyroscope.configure.side_effect = Exception("connection refused")
    with patch.object(pp, "GRAFANA_PROFILES_URL", "https://profiles.example.com"), \
         patch.object(pp, "GRAFANA_PROFILES_USER", "profiles-user"), \
         patch.object(pp, "GRAFANA_API_KEY", "api-key"), \
         patch.dict("sys.modules", {"pyroscope": mock_pyroscope}):
        pp.setup_profiling("local")  # must not raise


def test_setup_profiling_leaves_profiling_disabled_on_failure():
    from src.infrastructure.shared.observability import pyroscope_profiling as pp
    mock_pyroscope = MagicMock()
    mock_pyroscope.configure.side_effect = Exception("connection refused")
    with patch.object(pp, "_profiling_enabled", False), \
         patch.object(pp, "GRAFANA_PROFILES_URL", "https://profiles.example.com"), \
         patch.object(pp, "GRAFANA_PROFILES_USER", "profiles-user"), \
         patch.object(pp, "GRAFANA_API_KEY", "api-key"), \
         patch.dict("sys.modules", {"pyroscope": mock_pyroscope}):
        pp.setup_profiling("local")
        assert pp._profiling_enabled is False


def test_setup_profiling_enables_profiling_on_success():
    from src.infrastructure.shared.observability import pyroscope_profiling as pp
    mock_pyroscope = MagicMock()
    with patch.object(pp, "_profiling_enabled", False), \
         patch.object(pp, "GRAFANA_PROFILES_URL", "https://profiles.example.com"), \
         patch.object(pp, "GRAFANA_PROFILES_USER", "profiles-user"), \
         patch.object(pp, "GRAFANA_API_KEY", "api-key"), \
         patch.dict("sys.modules", {"pyroscope": mock_pyroscope}):
        pp.setup_profiling("production")
        assert pp._profiling_enabled is True


# ---------------------------------------------------------------------------
# shutdown_profiling
# ---------------------------------------------------------------------------

def test_shutdown_profiling_noop_when_never_enabled():
    from src.infrastructure.shared.observability import pyroscope_profiling as pp
    mock_pyroscope = MagicMock()
    with patch.object(pp, "_profiling_enabled", False), \
         patch.dict("sys.modules", {"pyroscope": mock_pyroscope}):
        pp.shutdown_profiling()
    mock_pyroscope.shutdown.assert_not_called()


def test_shutdown_profiling_calls_pyroscope_shutdown_when_enabled():
    from src.infrastructure.shared.observability import pyroscope_profiling as pp
    mock_pyroscope = MagicMock()
    with patch.object(pp, "_profiling_enabled", True), \
         patch.dict("sys.modules", {"pyroscope": mock_pyroscope}):
        pp.shutdown_profiling()
    mock_pyroscope.shutdown.assert_called_once()


def test_shutdown_profiling_swallows_exception():
    from src.infrastructure.shared.observability import pyroscope_profiling as pp
    mock_pyroscope = MagicMock()
    mock_pyroscope.shutdown.side_effect = Exception("already stopped")
    with patch.object(pp, "_profiling_enabled", True), \
         patch.dict("sys.modules", {"pyroscope": mock_pyroscope}):
        pp.shutdown_profiling()  # must not raise


# ---------------------------------------------------------------------------
# _current_span_tags / run_tagged_for_profiling
# ---------------------------------------------------------------------------

def test_current_span_tags_empty_without_active_span():
    from src.infrastructure.shared.observability.pyroscope_profiling import _current_span_tags
    assert _current_span_tags() == {}


def test_current_span_tags_returns_span_id_with_active_span():
    from src.infrastructure.shared.observability.pyroscope_profiling import _current_span_tags
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("test.span"):
        tags = _current_span_tags()
    assert list(tags.keys()) == ["span_id"]
    assert len(tags["span_id"]) == 16


def test_run_tagged_for_profiling_runs_func_when_profiling_disabled():
    from src.infrastructure.shared.observability import pyroscope_profiling as pp
    with patch.object(pp, "_profiling_enabled", False):
        result = pp.run_tagged_for_profiling(lambda: 42)
    assert result == 42


def test_run_tagged_for_profiling_runs_func_without_active_span():
    """Profiling enabled but no OTel span active — still just calls func(), no tagging
    attempted."""
    from src.infrastructure.shared.observability import pyroscope_profiling as pp
    with patch.object(pp, "_profiling_enabled", True):
        result = pp.run_tagged_for_profiling(lambda: 42)
    assert result == 42


def test_run_tagged_for_profiling_tags_thread_with_current_span_id():
    from src.infrastructure.shared.observability import pyroscope_profiling as pp
    from opentelemetry.sdk.trace import TracerProvider

    mock_pyroscope = MagicMock()
    provider = TracerProvider()
    tracer = provider.get_tracer("test")

    with patch.object(pp, "_profiling_enabled", True), \
         patch.dict("sys.modules", {"pyroscope": mock_pyroscope}):
        with tracer.start_as_current_span("test.span") as span:
            span_id = format(span.get_span_context().span_id, "016x")
            result = pp.run_tagged_for_profiling(lambda: 10)

    assert result == 10
    mock_pyroscope.tag_wrapper.assert_called_once_with({"span_id": span_id})
    mock_pyroscope.tag_wrapper.return_value.__enter__.assert_called_once()
    mock_pyroscope.tag_wrapper.return_value.__exit__.assert_called_once()


def test_run_tagged_for_profiling_still_runs_func_when_tagging_fails():
    """A pyroscope native-lib hiccup while tagging must not prevent func from running —
    profiling is best-effort everywhere else in this module, this helper is no exception."""
    from src.infrastructure.shared.observability import pyroscope_profiling as pp
    from opentelemetry.sdk.trace import TracerProvider

    mock_pyroscope = MagicMock()
    mock_pyroscope.tag_wrapper.side_effect = Exception("native lib error")
    provider = TracerProvider()
    tracer = provider.get_tracer("test")

    with patch.object(pp, "_profiling_enabled", True), \
         patch.dict("sys.modules", {"pyroscope": mock_pyroscope}):
        with tracer.start_as_current_span("test.span"):
            result = pp.run_tagged_for_profiling(lambda: 10)

    assert result == 10


def test_run_tagged_for_profiling_propagates_func_exception():
    from src.infrastructure.shared.observability import pyroscope_profiling as pp

    def _boom():
        raise ValueError("boom")

    with patch.object(pp, "_profiling_enabled", False):
        with pytest.raises(ValueError, match="boom"):
            pp.run_tagged_for_profiling(_boom)
