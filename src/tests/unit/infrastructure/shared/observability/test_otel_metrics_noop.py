"""Tests for OTel metrics no-op fallback and instrument behavior."""
import importlib
from unittest.mock import patch, MagicMock


def test_dummy_counter_add_is_noop():
    """_Dummy.add() must not raise and returns None."""
    from src.infrastructure.shared.observability.otel_metrics import _Dummy
    d = _Dummy()
    result = d.add(1, {"source": "rss"})
    assert result is None


def test_dummy_histogram_record_is_noop():
    """_Dummy.record() must not raise and returns None."""
    from src.infrastructure.shared.observability.otel_metrics import _Dummy
    d = _Dummy()
    result = d.record(3.14)
    assert result is None


def test_metrics_become_dummy_without_env(monkeypatch):
    """When GRAFANA_OTLP_* env vars are missing, all 6 metrics are _Dummy instances."""
    monkeypatch.delenv("GRAFANA_OTLP_USER", raising=False)
    monkeypatch.delenv("GRAFANA_API_KEY", raising=False)
    monkeypatch.delenv("GRAFANA_OTLP_ENDPOINT", raising=False)
    from src.infrastructure.shared.observability import otel_metrics
    importlib.reload(otel_metrics)
    from src.infrastructure.shared.observability.otel_metrics import _Dummy
    assert isinstance(otel_metrics.SCRAPER_RUNS, _Dummy)
    assert isinstance(otel_metrics.SCRAPER_DURATION, _Dummy)
    assert isinstance(otel_metrics.SCRAPER_ARTICLES_FOUND, _Dummy)
    assert isinstance(otel_metrics.SCRAPER_ARTICLES_NEW, _Dummy)
    assert isinstance(otel_metrics.SCRAPER_ARTICLES_DUPLICATE, _Dummy)
    assert isinstance(otel_metrics.SCRAPER_ERRORS, _Dummy)


def test_scraper_runs_counter_incremented_on_start():
    """CLI entrypoint calls SCRAPER_RUNS.add(1) at startup."""
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_span.__enter__ = MagicMock(return_value=mock_span)
    mock_span.__exit__ = MagicMock(return_value=False)
    mock_tracer.start_as_current_span.return_value = mock_span
    with patch("src.entrypoints.cli.main.SCRAPER_RUNS") as mock_runs, \
         patch("src.entrypoints.cli.main.validate_config"), \
         patch("src.entrypoints.cli.main.configure_logging"), \
         patch("src.entrypoints.cli.main.init_default_client"), \
         patch("src.entrypoints.cli.main.init_run_context", return_value=("rid", "cid")), \
         patch("src.entrypoints.cli.main.bind_correlation_id"), \
         patch("src.entrypoints.cli.main.SCRAPER_DURATION"), \
         patch("src.entrypoints.cli.main.push_metrics"), \
         patch("src.infrastructure.shared.observability.shutdown_tracing"), \
         patch("src.infrastructure.shared.observability.get_tracer", return_value=mock_tracer), \
         patch.dict("os.environ", {"RUN_IMMEDIATELY": "1"}), \
         patch("src.bootstrap.build_collection_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = None
        mock_build.return_value = mock_pipeline
        from src.entrypoints.cli.main import main
        main()
    mock_runs.add.assert_called_with(1)


def test_scraper_duration_recorded_on_exit():
    """CLI entrypoint calls SCRAPER_DURATION.record(duration) in finally block."""
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_span.__enter__ = MagicMock(return_value=mock_span)
    mock_span.__exit__ = MagicMock(return_value=False)
    mock_tracer.start_as_current_span.return_value = mock_span
    with patch("src.entrypoints.cli.main.SCRAPER_RUNS"), \
         patch("src.entrypoints.cli.main.validate_config"), \
         patch("src.entrypoints.cli.main.configure_logging"), \
         patch("src.entrypoints.cli.main.init_default_client"), \
         patch("src.entrypoints.cli.main.init_run_context", return_value=("rid", "cid")), \
         patch("src.entrypoints.cli.main.bind_correlation_id"), \
         patch("src.entrypoints.cli.main.SCRAPER_DURATION") as mock_duration, \
         patch("src.entrypoints.cli.main.push_metrics"), \
         patch("src.infrastructure.shared.observability.shutdown_tracing"), \
         patch("src.infrastructure.shared.observability.get_tracer", return_value=mock_tracer), \
         patch.dict("os.environ", {"RUN_IMMEDIATELY": "1"}), \
         patch("src.bootstrap.build_collection_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = None
        mock_build.return_value = mock_pipeline
        from src.entrypoints.cli.main import main
        main()
    mock_duration.record.assert_called_once()
    assert mock_duration.record.call_args[0][0] >= 0


def test_push_metrics_called_on_exit():
    """CLI entrypoint calls push_metrics() during process shutdown."""
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_span.__enter__ = MagicMock(return_value=mock_span)
    mock_span.__exit__ = MagicMock(return_value=False)
    mock_tracer.start_as_current_span.return_value = mock_span
    with patch("src.entrypoints.cli.main.SCRAPER_RUNS"), \
         patch("src.entrypoints.cli.main.validate_config"), \
         patch("src.entrypoints.cli.main.configure_logging"), \
         patch("src.entrypoints.cli.main.init_default_client"), \
         patch("src.entrypoints.cli.main.init_run_context", return_value=("rid", "cid")), \
         patch("src.entrypoints.cli.main.bind_correlation_id"), \
         patch("src.entrypoints.cli.main.SCRAPER_DURATION"), \
         patch("src.entrypoints.cli.main.push_metrics") as mock_push, \
         patch("src.infrastructure.shared.observability.shutdown_tracing"), \
         patch("src.infrastructure.shared.observability.get_tracer", return_value=mock_tracer), \
         patch.dict("os.environ", {"RUN_IMMEDIATELY": "1"}), \
         patch("src.bootstrap.build_collection_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = None
        mock_build.return_value = mock_pipeline
        from src.entrypoints.cli.main import main
        main()
    mock_push.assert_called_once()
