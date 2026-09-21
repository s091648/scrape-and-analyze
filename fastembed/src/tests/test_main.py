"""Tests for fastembed_service/main.py — app wiring, lifespan, and conditional
OTel instrumentation.

main.py runs its logging/tracing setup at *import* time (module-level calls,
not inside a function), so exercising the "tracer configured" vs. "not
configured" branches requires reloading the module with
fastembed_service.observability.configure_logging/setup_tracing patched
first — importlib.reload() re-executes `from fastembed_service.observability
import configure_logging, setup_tracing`, which re-binds to whatever those
names currently point to. Patching fastembed_service.main's own names
wouldn't work: reload() overwrites them via that same import statement before
main's own top-level code runs. Mirrors backend/tests/test_main.py's reload
pattern for the same reason (module-level env-dependent wiring).
"""
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _clear_root_handlers():
    import logging
    root = logging.getLogger()
    handlers = root.handlers[:]
    for h in handlers:
        root.removeHandler(h)
    return handlers


def _restore_root_handlers(handlers):
    import logging
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    for h in handlers:
        root.addHandler(h)


@pytest.fixture
def reload_main():
    """Reloads fastembed_service.main with observability's setup functions
    patched, yields the fresh module, then reloads back to the real
    (env-driven) state so later tests/files see production wiring again."""
    original_handlers = _clear_root_handlers()
    modules = []

    def _do(configure_logging_mock=None, setup_tracing_return=None):
        import fastembed_service.observability as observability
        with patch.object(observability, "configure_logging", configure_logging_mock or MagicMock()), \
             patch.object(observability, "setup_tracing", MagicMock(return_value=setup_tracing_return)):
            import fastembed_service.main as main
            importlib.reload(main)
        modules.append(main)
        return main

    yield _do

    _restore_root_handlers(original_handlers)
    if modules:
        importlib.reload(modules[0])  # restore real wiring for subsequent test files


def test_app_includes_embed_router_routes(reload_main):
    main = reload_main()
    paths = {route.path for route in main.app.routes}
    assert "/health" in paths
    assert "/embed" in paths


def test_configure_logging_called_with_service_name(reload_main):
    mock_configure = MagicMock()
    reload_main(configure_logging_mock=mock_configure)
    mock_configure.assert_called_once()
    _, kwargs = mock_configure.call_args
    assert kwargs["service"] == "fastembed"


def test_instrumentation_skipped_without_tracer_provider(reload_main):
    with patch(
        "opentelemetry.instrumentation.fastapi.FastAPIInstrumentor.instrument_app"
    ) as mock_instrument:
        reload_main(setup_tracing_return=None)
    mock_instrument.assert_not_called()


def test_instrumentation_applied_with_tracer_provider(reload_main):
    mock_provider = MagicMock()
    with patch(
        "opentelemetry.instrumentation.fastapi.FastAPIInstrumentor.instrument_app"
    ) as mock_instrument:
        main = reload_main(setup_tracing_return=mock_provider)
    mock_instrument.assert_called_once_with(main.app, tracer_provider=mock_provider)


@pytest.mark.asyncio
async def test_lifespan_loads_embedding_service_and_sets_app_state(reload_main):
    main = reload_main()
    main._embedding_service.load = AsyncMock()

    async with main.lifespan(main.app):
        pass

    main._embedding_service.load.assert_awaited_once()
    assert main.app.state.embedding_service is main._embedding_service


@pytest.mark.asyncio
async def test_lifespan_shuts_down_tracer_provider_on_exit(reload_main):
    mock_provider = MagicMock()
    with patch("opentelemetry.instrumentation.fastapi.FastAPIInstrumentor.instrument_app"):
        main = reload_main(setup_tracing_return=mock_provider)
    main._embedding_service.load = AsyncMock()

    async with main.lifespan(main.app):
        pass

    mock_provider.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_skips_shutdown_when_no_tracer_provider(reload_main):
    """No provider to shut down -> must not raise on None.shutdown()."""
    main = reload_main(setup_tracing_return=None)
    main._embedding_service.load = AsyncMock()

    async with main.lifespan(main.app):
        pass  # must not raise
