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

    async def _fake_listen():
        yield {"type": "subscribe", "data": 1}
        yield {"type": "message", "data": b"scraper_pipeline"}
        while True:
            await asyncio.sleep(3600)

    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.listen = _fake_listen

    mock_client = MagicMock()
    mock_client.pubsub = MagicMock(return_value=mock_pubsub)
    mock_client.aclose = AsyncMock()

    with patch("redis.asyncio.from_url", return_value=mock_client), \
         patch("backend.cache_warmup_listener.warm_default_reads", new_callable=AsyncMock) as mock_warm:
        await _run_briefly_then_cancel(listen_for_warmup_signals)

    mock_warm.assert_awaited_once_with("scraper_pipeline")


@pytest.mark.asyncio
async def test_listener_ignores_non_message_events():
    from backend.cache_warmup_listener import listen_for_warmup_signals

    async def _fake_listen():
        yield {"type": "subscribe", "data": 1}
        while True:
            await asyncio.sleep(3600)

    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.listen = _fake_listen

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

    async def _fake_listen():
        yield {"type": "message", "data": b"scraper_pipeline"}
        while True:
            await asyncio.sleep(3600)

    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.listen = _fake_listen

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

        async def _hang_listen():
            yield {"type": "subscribe", "data": 1}
            while True:
                await asyncio.sleep(3600)
        mock_pubsub.listen = _hang_listen

        client = MagicMock()
        client.pubsub = MagicMock(return_value=mock_pubsub)
        client.aclose = AsyncMock()
        return client

    with patch("redis.asyncio.from_url", side_effect=_from_url), \
         patch("backend.cache_warmup_listener.warm_default_reads", new_callable=AsyncMock), \
         patch("backend.cache_warmup_listener._RECONNECT_DELAY_SECONDS", 0.01):
        await _run_briefly_then_cancel(listen_for_warmup_signals)

    assert attempt["count"] >= 2  # first attempt failed, loop reconnected at least once
