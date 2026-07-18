"""Unit tests for backend/main.py: periodic view-count flush task, lifespan wiring,
and router registration."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _periodic_view_flush
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_periodic_view_flush_calls_flush_view_counts_each_iteration():
    from backend.main import _periodic_view_flush

    fake_db = MagicMock()
    mock_flush = AsyncMock(return_value=3)

    # sleep succeeds twice, then raises CancelledError to end the infinite loop.
    sleep_mock = AsyncMock(side_effect=[None, None, asyncio.CancelledError()])

    with patch("backend.main.SessionLocal", return_value=fake_db), \
         patch("backend.services.article_service.flush_view_counts", mock_flush), \
         patch("asyncio.sleep", sleep_mock):
        with pytest.raises(asyncio.CancelledError):
            await _periodic_view_flush()

    assert mock_flush.await_count == 2
    assert fake_db.close.call_count == 2


@pytest.mark.asyncio
async def test_periodic_view_flush_swallows_exceptions_and_continues():
    from backend.main import _periodic_view_flush

    fake_db = MagicMock()
    # First call raises, second call succeeds — the loop must survive the exception
    # and keep running (a single bad flush shouldn't kill the background task).
    mock_flush = AsyncMock(side_effect=[RuntimeError("boom"), None])
    sleep_mock = AsyncMock(side_effect=[None, None, asyncio.CancelledError()])

    with patch("backend.main.SessionLocal", return_value=fake_db), \
         patch("backend.services.article_service.flush_view_counts", mock_flush), \
         patch("asyncio.sleep", sleep_mock):
        with pytest.raises(asyncio.CancelledError):
            await _periodic_view_flush()

    assert mock_flush.await_count == 2
    # db.close() still called on both iterations (finally block), including the errored one.
    assert fake_db.close.call_count == 2


@pytest.mark.asyncio
async def test_periodic_view_flush_closes_db_even_on_exception():
    from backend.main import _periodic_view_flush

    fake_db = MagicMock()
    mock_flush = AsyncMock(side_effect=RuntimeError("boom"))
    sleep_mock = AsyncMock(side_effect=[None, asyncio.CancelledError()])

    with patch("backend.main.SessionLocal", return_value=fake_db), \
         patch("backend.services.article_service.flush_view_counts", mock_flush), \
         patch("asyncio.sleep", sleep_mock):
        with pytest.raises(asyncio.CancelledError):
            await _periodic_view_flush()

    fake_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# lifespan
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lifespan_starts_and_cancels_background_task():
    from backend.main import lifespan, app

    fake_task = MagicMock()

    def fake_create_task(coro):
        coro.close()  # avoid "coroutine was never awaited" warning; we don't run it here
        return fake_task

    with patch("asyncio.create_task", side_effect=fake_create_task) as mock_create_task:
        async with lifespan(app):
            mock_create_task.assert_called_once()

    fake_task.cancel.assert_called_once()


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------

def test_new_routers_are_registered():
    from backend.main import app

    paths = {route.path for route in app.routes}
    assert "/user/favorites" in paths
    assert "/weekly-reports" in paths
    assert "/weekly-reports/latest" in paths
    assert "/metric-definitions" in paths
    assert "/admin/metric-definitions" in paths
