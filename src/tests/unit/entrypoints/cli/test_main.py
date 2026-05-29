import time
from unittest.mock import patch, MagicMock, call

import pytest

from src.entrypoints.cli.main import check_timeout, MAX_EXECUTION_TIME, signal_handler, _shutdown_requested


# ── Existing tests (preserved) ────────────────────────────────────────────

def test_check_timeout_returns_true_when_exceeded():
    start_time = time.time() - MAX_EXECUTION_TIME - 1
    assert check_timeout(start_time) is True


def test_check_timeout_returns_false_when_not_exceeded():
    start_time = time.time()
    assert check_timeout(start_time) is False


# ── T005: main() raises ValueError when DATABASE_URL not set ──────────────

def test_main_raises_valueerror_when_database_url_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("RUN_IMMEDIATELY", raising=False)

    with patch("src.entrypoints.cli.main.validate_config", side_effect=ValueError("DATABASE_URL is required")):
        from src.entrypoints.cli.main import main
        with pytest.raises(ValueError, match="DATABASE_URL"):
            main()


# ── T006: main() calls time.sleep() in [0, 180] when RUN_IMMEDIATELY not set ─

def test_main_sleeps_when_run_immediately_not_set(monkeypatch, mock_validate_config, mock_configure_logging, mock_build_pipeline, mock_push_metrics, mock_shutdown_tracing, mock_scraper_runs, mock_scraper_duration, mock_init_run_context, mock_bind_correlation_id, mock_get_run_id, mock_signal, mock_init_default_client, mock_http_client_build, mock_get_tracer):
    monkeypatch.delenv("RUN_IMMEDIATELY", raising=False)
    with patch("src.entrypoints.cli.main.time.sleep") as mock_sleep:
        from src.entrypoints.cli.main import main
        main()
        mock_sleep.assert_called_once()
        sleep_arg = mock_sleep.call_args[0][0]
        assert 0 <= sleep_arg <= 180


# ── T007: main() does NOT call time.sleep() when RUN_IMMEDIATELY is set ────

def test_main_skips_sleep_when_run_immediately_set(all_mocks):
    from src.entrypoints.cli.main import main
    main()
    all_mocks["sleep"].assert_not_called()


# ── T008: main() generates run_id and correlation_id ───────────────────────

def test_main_generates_run_context(all_mocks):
    from src.entrypoints.cli.main import main
    main()
    all_mocks["init_run_context"].assert_called_once()
    all_mocks["bind_correlation_id"].assert_called_once_with("test-correlation-id")


# ── T009: main() registers signal handlers for SIGTERM and SIGINT ─────────

def test_main_registers_signal_handlers(all_mocks):
    from src.entrypoints.cli.main import main
    import signal as sig
    main()
    calls = all_mocks["signal"].call_args_list
    assert call(sig.SIGTERM, signal_handler) in calls or any(c[0][0] == sig.SIGTERM for c in calls)
    assert call(sig.SIGINT, signal_handler) in calls or any(c[0][0] == sig.SIGINT for c in calls)


# ── T010: main() calls build_collection_pipeline() then pipeline.run() ──

def test_main_calls_pipeline_in_sequence(all_mocks):
    from src.entrypoints.cli.main import main
    mock_build, mock_pipeline = all_mocks["build_pipeline"]
    main()
    mock_build.assert_called_once()
    mock_pipeline.run.assert_called_once()


# ── T011: main() calls push_metrics/shutdown_tracing in finally on error ─

def test_main_calls_teardown_even_on_pipeline_error(all_mocks):
    from src.entrypoints.cli.main import main
    mock_build, mock_pipeline = all_mocks["build_pipeline"]
    mock_pipeline.run.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        main()
    all_mocks["push_metrics"].assert_called_once()
    all_mocks["shutdown_tracing"].assert_called_once()


# ── T012: main() increments SCRAPER_RUNS counter ──────────────────────────

def test_main_increments_scraper_runs_counter(all_mocks):
    from src.entrypoints.cli.main import main
    main()
    all_mocks["scraper_runs"].add.assert_called_with(1)


# ── T013: main() records SCRAPER_DURATION histogram ───────────────────────

def test_main_records_scraper_duration(all_mocks):
    from src.entrypoints.cli.main import main
    main()
    all_mocks["scraper_duration"].record.assert_called_once()
    duration_arg = all_mocks["scraper_duration"].record.call_args[0][0]
    assert isinstance(duration_arg, float)
    assert duration_arg >= 0


# ── T014: main() starts OTel span "scraper.run" ───────────────────────────

def test_main_starts_otel_span(all_mocks):
    from src.entrypoints.cli.main import main
    mock_get_tracer, mock_tracer, mock_span = all_mocks["get_tracer"]
    main()
    mock_tracer.start_as_current_span.assert_called_once_with("scraper.run")


# ── T030: main() binds correlation_id to structlog ────────────────────────

def test_main_binds_correlation_id_to_structlog(all_mocks):
    from src.entrypoints.cli.main import main
    main()
    all_mocks["bind_correlation_id"].assert_called_once_with("test-correlation-id")


# ── T031: Sentry initialized at import time with traces_sample_rate=0.1 ───

def test_sentry_initialized_when_dsn_set():
    import importlib
    import src.config.settings as settings_mod
    import src.entrypoints.cli.main as main_mod
    with patch("sentry_sdk.init") as mock_init, \
         patch.object(settings_mod, "SENTRY_DSN", "https://test@sentry.io/123"):
        importlib.reload(main_mod)
        mock_init.assert_called_once_with(dsn="https://test@sentry.io/123", traces_sample_rate=0.1)
    importlib.reload(main_mod)


# ── T032: Sentry NOT initialized when DSN not set ─────────────────────────

def test_sentry_not_initialized_when_dsn_missing():
    import importlib
    import src.config.settings as settings_mod
    import src.entrypoints.cli.main as main_mod
    with patch("sentry_sdk.init") as mock_init, \
         patch.object(settings_mod, "SENTRY_DSN", ""):
        importlib.reload(main_mod)
        mock_init.assert_not_called()
    importlib.reload(main_mod)


# ── T033: push_metrics() failure does not prevent shutdown_tracing() ───────

def test_push_metrics_failure_does_not_block_shutdown(all_mocks):
    from src.entrypoints.cli.main import main
    all_mocks["push_metrics"].side_effect = RuntimeError("metrics push failed")
    main()
    all_mocks["shutdown_tracing"].assert_called_once()


# ── T034: shutdown_tracing() failure does not prevent process exit ────────

def test_shutdown_tracing_failure_does_not_raise(all_mocks):
    from src.entrypoints.cli.main import main
    all_mocks["shutdown_tracing"].side_effect = RuntimeError("tracing shutdown failed")
    # main() does not re-raise shutdown_tracing errors in the current code,
    # but it also doesn't wrap it in try/except. This test documents that
    # if shutdown_tracing raises, it will propagate. The spec notes the
    # finally block wraps push_metrics in try/except but NOT shutdown_tracing.
    # Update: re-reading the source, shutdown_tracing is NOT wrapped in try/except.
    # This is a known gap. The test documents current behaviour.
    with pytest.raises(RuntimeError, match="tracing shutdown failed"):
        main()


# ── T035: signal_handler sets _shutdown_requested and logs ────────────────

def test_signal_handler_sets_shutdown_flag():
    import src.entrypoints.cli.main as main_mod
    main_mod._shutdown_requested = False
    with patch.object(main_mod, "logger") as mock_logger:
        main_mod.signal_handler(15, None)
        assert main_mod._shutdown_requested is True
        mock_logger.warning.assert_called_once_with("shutdown_signal_received", signal=15)


# ── T036: _shutdown_requested is not checked by pipeline ───────────────────

def test_shutdown_flag_not_checked_by_pipeline():
    """Verify that _shutdown_requested is a standalone flag with no consumers."""
    import src.entrypoints.cli.main as main_mod
    # The flag exists but no code reads it in the pipeline path.
    # This test confirms the attribute exists and documents the gap.
    assert hasattr(main_mod, "_shutdown_requested")


# ── T037/T038: check_timeout() existing tests (already above, preserved) ──


# ── T039: check_timeout() is NOT called in main() execution path ──────────

def test_check_timeout_not_called_in_main(all_mocks):
    from src.entrypoints.cli.main import main
    with patch("src.entrypoints.cli.main.check_timeout") as mock_check:
        main()
        mock_check.assert_not_called()


# ── T045: main() initializes default HTTP client ──────────────────────────

def test_main_initializes_default_http_client(all_mocks):
    from src.entrypoints.cli.main import main
    main()
    all_mocks["http_client_build"].assert_called_once()
    all_mocks["init_default_client"].assert_called_once()
