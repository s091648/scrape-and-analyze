"""Unit tests for backend/cache_warmup_listener.py — the background asyncio task that listens
for the cache-warmup Pub/Sub signal (020-redis-caching-layer follow-up)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def _run_briefly_then_cancel(coro_factory, delay: float = 0.05):
    task = asyncio.create_task(coro_factory())
    await asyncio.sleep(delay)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_listener_warms_on_message():
    from backend.cache_warmup_listener import listen_for_warmup_signals

    call_count = {"n": 0}

    async def _fake_get_message(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"type": "message", "data": b"scraper_pipeline"}
        await asyncio.sleep(3600)

    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.get_message = _fake_get_message

    mock_client = MagicMock()
    mock_client.pubsub = MagicMock(return_value=mock_pubsub)
    mock_client.aclose = AsyncMock()

    with patch("redis.asyncio.from_url", return_value=mock_client), \
         patch("backend.cache_warmup_listener.warm_default_reads", new_callable=AsyncMock) as mock_warm:
        await _run_briefly_then_cancel(listen_for_warmup_signals)

    mock_warm.assert_awaited_once_with("scraper_pipeline")


@pytest.mark.asyncio
async def test_listener_ignores_non_message_events():
    """get_message(ignore_subscribe_messages=True, ...) returns None for a subscribe
    confirmation (and for a plain poll timeout with nothing new) — neither should trigger a
    warmup run."""
    from backend.cache_warmup_listener import listen_for_warmup_signals

    async def _fake_get_message(*args, **kwargs):
        await asyncio.sleep(0)  # yield control each poll cycle, like a real timed-out poll
        return None

    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.get_message = _fake_get_message

    mock_client = MagicMock()
    mock_client.pubsub = MagicMock(return_value=mock_pubsub)
    mock_client.aclose = AsyncMock()

    with patch("redis.asyncio.from_url", return_value=mock_client), \
         patch("backend.cache_warmup_listener.warm_default_reads", new_callable=AsyncMock) as mock_warm:
        await _run_briefly_then_cancel(listen_for_warmup_signals)

    mock_warm.assert_not_awaited()


@pytest.mark.asyncio
async def test_listener_survives_a_failing_warmup_run():
    """A warm_default_reads() failure must not kill the listener loop — it should keep
    listening for the next signal."""
    from backend.cache_warmup_listener import listen_for_warmup_signals

    call_count = {"n": 0}

    async def _fake_get_message(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"type": "message", "data": b"scraper_pipeline"}
        await asyncio.sleep(3600)

    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.get_message = _fake_get_message

    mock_client = MagicMock()
    mock_client.pubsub = MagicMock(return_value=mock_pubsub)
    mock_client.aclose = AsyncMock()

    with patch("redis.asyncio.from_url", return_value=mock_client), \
         patch("backend.cache_warmup_listener.warm_default_reads", new_callable=AsyncMock) as mock_warm:
        mock_warm.side_effect = Exception("boom")
        await _run_briefly_then_cancel(listen_for_warmup_signals)

    mock_warm.assert_awaited_once()


@pytest.mark.asyncio
async def test_listener_reconnects_after_redis_error_without_raising():
    from backend.cache_warmup_listener import listen_for_warmup_signals

    attempt = {"count": 0}

    def _from_url(*args, **kwargs):
        attempt["count"] += 1
        if attempt["count"] == 1:
            raise ConnectionError("redis down")
        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()

        async def _hang_get_message(*a, **kw):
            await asyncio.sleep(3600)
        mock_pubsub.get_message = _hang_get_message

        client = MagicMock()
        client.pubsub = MagicMock(return_value=mock_pubsub)
        client.aclose = AsyncMock()
        return client

    with patch("redis.asyncio.from_url", side_effect=_from_url), \
         patch("backend.cache_warmup_listener.warm_default_reads", new_callable=AsyncMock), \
         patch("backend.cache_warmup_listener._RECONNECT_DELAY_SECONDS", 0.01):
        await _run_briefly_then_cancel(listen_for_warmup_signals)

    assert attempt["count"] >= 2  # first attempt failed, loop reconnected at least once


@pytest.mark.asyncio
async def test_listener_passes_health_check_interval_to_from_url():
    """The whole fix for the ~10s disconnect cycle hinges on redis-py's periodic PING
    keep-alive being enabled — a regression here would silently reintroduce the bug."""
    from backend.cache_warmup_listener import listen_for_warmup_signals, _HEALTH_CHECK_INTERVAL_SECONDS

    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()

    async def _hang_get_message(*a, **kw):
        await asyncio.sleep(3600)
    mock_pubsub.get_message = _hang_get_message

    mock_client = MagicMock()
    mock_client.pubsub = MagicMock(return_value=mock_pubsub)
    mock_client.aclose = AsyncMock()

    with patch("redis.asyncio.from_url", return_value=mock_client) as mock_from_url, \
         patch("backend.cache_warmup_listener.warm_default_reads", new_callable=AsyncMock):
        await _run_briefly_then_cancel(listen_for_warmup_signals)

    _, kwargs = mock_from_url.call_args
    assert kwargs.get("health_check_interval") == _HEALTH_CHECK_INTERVAL_SECONDS
