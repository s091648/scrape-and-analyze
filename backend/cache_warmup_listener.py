"""Background asyncio task that listens on Redis Pub/Sub for the cache-warmup signal
(shared.cache.CacheGateway.publish_warmup_signal(), published by src/'s CacheWarmupHandler and
GenerateWeeklyReportUseCase) and re-populates the default reads via backend's own ASGI app
(backend/cache_warmup.py) — the event-driven replacement for the HTTP self-call the scraper
process used to make against backend's own endpoints (020-redis-caching-layer follow-up).

Wired into backend/main.py's lifespan the same way as _periodic_view_flush: one
asyncio.create_task() at startup, cancelled at shutdown.
"""
import asyncio

import redis.asyncio as aioredis
import structlog

from shared.cache import WARMUP_CHANNEL
from backend.cache_warmup import warm_default_reads
from backend.config import CACHE_REDIS_URL

logger = structlog.get_logger()

_RECONNECT_DELAY_SECONDS = 5


async def listen_for_warmup_signals() -> None:
    """Runs forever until cancelled at app shutdown. Reconnects on any Redis error after a
    fixed delay — Pub/Sub has no message persistence, so a dropped connection just means the
    next visitor after a missed signal pays one ordinary cache-miss cost, never a correctness
    issue (bump_version() has already made the stale entries unreachable regardless)."""
    while True:
        client = None
        try:
            client = aioredis.from_url(CACHE_REDIS_URL)
            pubsub = client.pubsub()
            await pubsub.subscribe(WARMUP_CHANNEL)
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                raw_reason = message.get("data")
                reason = raw_reason.decode() if isinstance(raw_reason, bytes) else str(raw_reason or "")
                try:
                    await warm_default_reads(reason)
                except Exception as e:
                    logger.warning("cache_warmup_run_failed", reason=reason, error=str(e))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("cache_warmup_listener_disconnected", error=str(e))
            await asyncio.sleep(_RECONNECT_DELAY_SECONDS)
        finally:
            if client is not None:
                try:
                    await client.aclose()
                except Exception:
                    pass
