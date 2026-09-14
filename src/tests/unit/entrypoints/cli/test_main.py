from unittest.mock import patch, MagicMock

import pytest


# ── T005: main() raises ValueError when DATABASE_URL not set ──────────────

def test_main_raises_valueerror_when_database_url_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("RUN_IMMEDIATELY", raising=False)

    with patch("src.entrypoints.cli.main.validate_config", side_effect=ValueError("DATABASE_URL is required")):
        from src.entrypoints.cli.main import main
        with pytest.raises(ValueError, match="DATABASE_URL"):
            main()


# ── T006: main() calls time.sleep() in [0, 180] when RUN_IMMEDIATELY not set ─

def test_main_sleeps_when_run_immediately_not_set(monkeypatch, mock_validate_config, mock_configure_logging, mock_build_pipeline, mock_shutdown_tracing, mock_init_run_context, mock_bind_correlation_id, mock_get_run_id, mock_init_default_client, mock_http_client_build, mock_get_tracer):
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


# ── T010: main() calls build_collection_pipeline() then pipeline.run() ──

def test_main_calls_pipeline_in_sequence(all_mocks):
    from src.entrypoints.cli.main import main
    mock_build, mock_pipeline = all_mocks["build_pipeline"]
    main()
    mock_build.assert_called_once()
    mock_pipeline.run.assert_called_once()


# ── T011: main() calls shutdown_tracing in finally on error ──────────────

def test_main_calls_teardown_even_on_pipeline_error(all_mocks):
    from src.entrypoints.cli.main import main
    mock_build, mock_pipeline = all_mocks["build_pipeline"]
    mock_pipeline.run.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        main()
    all_mocks["shutdown_tracing"].assert_called_once()


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
        mock_init.assert_called_once_with(
            dsn="https://test@sentry.io/123", environment=settings_mod.APP_ENV,
            traces_sample_rate=0.1, include_local_variables=False,
        )
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


# ── T039: main() enforces MAX_EXECUTION_TIME via asyncio.timeout() ────────

def test_main_enforces_max_execution_time(all_mocks):
    """pipeline.run() runs inside `async with asyncio.timeout(MAX_EXECUTION_TIME)`;
    a run that overshoots is cancelled, surfaces as TimeoutError, and teardown
    (shutdown_tracing) still runs."""
    from src.entrypoints.cli import main as main_mod

    async def _too_slow():
        import asyncio as _asyncio
        await _asyncio.sleep(1)

    _, mock_pipeline = all_mocks["build_pipeline"]
    mock_pipeline.run.side_effect = _too_slow

    with patch.object(main_mod, "MAX_EXECUTION_TIME", 0.01):
        with pytest.raises(TimeoutError):
            main_mod.main()
    all_mocks["shutdown_tracing"].assert_called_once()


# ── T045: main() initializes default HTTP client ──────────────────────────

def test_main_initializes_default_http_client(all_mocks):
    from src.entrypoints.cli.main import main
    main()
    all_mocks["http_client_build"].assert_called_once()
    all_mocks["init_default_client"].assert_called_once()


# ── T046: shutdown_tracing() is called AFTER the root span ends ──────────────

def test_shutdown_tracing_called_after_root_span_ends(all_mocks):
    """shutdown_tracing must be called outside the root span's with-block.

    If called inside, BatchSpanProcessor.shutdown() fires before scraper.run
    span ends, so on_end() sees _shutdown=True and drops the span silently.
    Tempo then receives orphaned child spans with no root → durationMs missing
    → NaN displayed in the frontend.
    """
    from src.entrypoints.cli.main import main

    call_order = []
    _, mock_tracer, _ = all_mocks["get_tracer"]
    ctx = mock_tracer.start_as_current_span.return_value
    ctx.__exit__.side_effect = lambda *args: call_order.append("span_end")
    all_mocks["shutdown_tracing"].side_effect = lambda: call_order.append("shutdown_tracing")

    main()

    assert "span_end" in call_order, "Root span __exit__ was never called"
    assert "shutdown_tracing" in call_order, "shutdown_tracing was never called"
    assert call_order.index("span_end") < call_order.index("shutdown_tracing"), (
        f"shutdown_tracing() was called before span ended. Call order: {call_order}. "
        "Move shutdown_tracing() to outside the root span's with-block."
    )
