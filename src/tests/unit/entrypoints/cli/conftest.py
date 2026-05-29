import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch):
    """Set required env vars so main() doesn't bail early."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    monkeypatch.setenv("RUN_IMMEDIATELY", "1")


@pytest.fixture()
def mock_time_sleep():
    with patch("src.entrypoints.cli.main.time.sleep") as m:
        yield m


@pytest.fixture()
def mock_validate_config():
    with patch("src.entrypoints.cli.main.validate_config") as m:
        yield m


@pytest.fixture()
def mock_configure_logging():
    with patch("src.entrypoints.cli.main.configure_logging") as m:
        yield m


@pytest.fixture()
def mock_build_pipeline():
    with patch("src.bootstrap.build_collection_pipeline") as m:
        pipeline = MagicMock()
        pipeline.run.return_value = 0
        m.return_value = pipeline
        yield m, pipeline


@pytest.fixture()
def mock_push_metrics():
    with patch("src.entrypoints.cli.main.push_metrics") as m:
        yield m


@pytest.fixture()
def mock_shutdown_tracing():
    with patch("src.infrastructure.shared.observability.shutdown_tracing") as m:
        yield m


@pytest.fixture()
def mock_scraper_runs():
    with patch("src.entrypoints.cli.main.SCRAPER_RUNS") as m:
        yield m


@pytest.fixture()
def mock_scraper_duration():
    with patch("src.entrypoints.cli.main.SCRAPER_DURATION") as m:
        yield m


@pytest.fixture()
def mock_init_run_context():
    with patch("src.entrypoints.cli.main.init_run_context") as m:
        m.return_value = ("test-run-id", "test-correlation-id")
        yield m


@pytest.fixture()
def mock_bind_correlation_id():
    with patch("src.entrypoints.cli.main.bind_correlation_id") as m:
        yield m


@pytest.fixture()
def mock_get_run_id():
    with patch("src.entrypoints.cli.main.get_run_id") as m:
        m.return_value = "test-run-id"
        yield m


@pytest.fixture()
def mock_signal():
    with patch("src.entrypoints.cli.main.signal.signal") as m:
        yield m


@pytest.fixture()
def mock_init_default_client():
    with patch("src.entrypoints.cli.main.init_default_client") as m:
        yield m


@pytest.fixture()
def mock_http_client_build():
    with patch("src.entrypoints.cli.main.HttpClient.build_default") as m:
        m.return_value = MagicMock()
        yield m


@pytest.fixture()
def mock_get_tracer():
    tracer = MagicMock()
    span = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = lambda s: span
    ctx.__exit__ = MagicMock(return_value=False)
    tracer.start_as_current_span.return_value = ctx
    with patch("src.infrastructure.shared.observability.get_tracer", return_value=tracer) as m:
        yield m, tracer, span


@pytest.fixture()
def mock_otel_trace():
    with patch.dict("sys.modules", {"opentelemetry.trace": MagicMock()}) as mod:
        trace_mod = mod["opentelemetry.trace"]
        trace_mod.StatusCode.ERROR = "ERROR"
        yield trace_mod


@pytest.fixture()
def all_mocks(
    mock_time_sleep,
    mock_validate_config,
    mock_configure_logging,
    mock_build_pipeline,
    mock_push_metrics,
    mock_shutdown_tracing,
    mock_scraper_runs,
    mock_scraper_duration,
    mock_init_run_context,
    mock_bind_correlation_id,
    mock_get_run_id,
    mock_signal,
    mock_init_default_client,
    mock_http_client_build,
    mock_get_tracer,
):
    """Bundle all mocks for tests that need the full main() lifecycle."""
    return {
        "sleep": mock_time_sleep,
        "validate_config": mock_validate_config,
        "configure_logging": mock_configure_logging,
        "build_pipeline": mock_build_pipeline,
        "push_metrics": mock_push_metrics,
        "shutdown_tracing": mock_shutdown_tracing,
        "scraper_runs": mock_scraper_runs,
        "scraper_duration": mock_scraper_duration,
        "init_run_context": mock_init_run_context,
        "bind_correlation_id": mock_bind_correlation_id,
        "get_run_id": mock_get_run_id,
        "signal": mock_signal,
        "init_default_client": mock_init_default_client,
        "http_client_build": mock_http_client_build,
        "get_tracer": mock_get_tracer,
    }
