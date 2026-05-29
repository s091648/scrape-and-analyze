"""Tests for OTel tracing no-op fallback and span lifecycle."""
import importlib
from unittest.mock import patch, MagicMock


def test_tracer_is_noop_without_env(monkeypatch):
    """When GRAFANA_OTLP_* env vars are missing, get_tracer() returns a valid Tracer."""
    monkeypatch.delenv("GRAFANA_OTLP_USER", raising=False)
    monkeypatch.delenv("GRAFANA_API_KEY", raising=False)
    monkeypatch.delenv("GRAFANA_OTLP_ENDPOINT", raising=False)
    from src.infrastructure.shared.observability import otel_tracing
    importlib.reload(otel_tracing)
    from opentelemetry import trace
    tracer = otel_tracing.get_tracer()
    assert isinstance(tracer, trace.Tracer)


def test_start_span_noop_without_provider():
    """start_as_current_span() does not raise when no provider is configured."""
    from src.infrastructure.shared.observability.otel_tracing import get_tracer
    tracer = get_tracer()
    with tracer.start_as_current_span("test.span") as span:
        assert span is not None


def test_scraper_run_span_created_with_attributes():
    """CLI entrypoint creates a span named 'scraper.run' with run.id and run.correlation_id."""
    with patch("src.entrypoints.cli.main.SCRAPER_RUNS"), \
         patch("src.entrypoints.cli.main.validate_config"), \
         patch("src.entrypoints.cli.main.configure_logging"), \
         patch("src.entrypoints.cli.main.init_default_client"), \
         patch("src.entrypoints.cli.main.init_run_context", return_value=("run-abc", "corr-xyz")), \
         patch("src.entrypoints.cli.main.bind_correlation_id"), \
         patch("src.entrypoints.cli.main.SCRAPER_DURATION"), \
         patch("src.entrypoints.cli.main.push_metrics"), \
         patch("src.entrypoints.cli.main.shutdown_tracing"), \
         patch.dict("os.environ", {"RUN_IMMEDIATELY": "1"}):
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_tracer.start_as_current_span.return_value = mock_span
        with patch("src.entrypoints.cli.main.get_tracer", return_value=mock_tracer), \
             patch("src.bootstrap.build_collection_pipeline") as mock_build:
            mock_pipeline = MagicMock()
            mock_pipeline.run.return_value = None
            mock_build.return_value = mock_pipeline
            from src.entrypoints.cli.main import main
            main()
    mock_tracer.start_as_current_span.assert_called_once_with("scraper.run")
    mock_span.set_attribute.assert_any_call("run.id", "run-abc")
    mock_span.set_attribute.assert_any_call("run.correlation_id", "corr-xyz")


def test_span_status_set_on_exception():
    """When the pipeline raises, span status is set to ERROR and exception is recorded."""
    with patch("src.entrypoints.cli.main.SCRAPER_RUNS"), \
         patch("src.entrypoints.cli.main.validate_config"), \
         patch("src.entrypoints.cli.main.configure_logging"), \
         patch("src.entrypoints.cli.main.init_default_client"), \
         patch("src.entrypoints.cli.main.init_run_context", return_value=("rid", "cid")), \
         patch("src.entrypoints.cli.main.bind_correlation_id"), \
         patch("src.entrypoints.cli.main.SCRAPER_DURATION"), \
         patch("src.entrypoints.cli.main.push_metrics"), \
         patch("src.entrypoints.cli.main.shutdown_tracing"), \
         patch.dict("os.environ", {"RUN_IMMEDIATELY": "1"}):
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_tracer.start_as_current_span.return_value = mock_span
        with patch("src.entrypoints.cli.main.get_tracer", return_value=mock_tracer), \
             patch("src.bootstrap.build_collection_pipeline") as mock_build:
            mock_pipeline = MagicMock()
            mock_pipeline.run.side_effect = RuntimeError("boom")
            mock_build.return_value = mock_pipeline
            from src.entrypoints.cli.main import main
            try:
                main()
            except RuntimeError:
                pass
    mock_span.record_exception.assert_called_once()
    mock_span.set_status.assert_called_once()
