"""Backend-side cache warm-up, triggered by a Redis Pub/Sub signal (see
cache_warmup_listener.py) instead of the cross-process HTTP self-call src/'s
CacheWarmupHandler used to make against backend's own endpoints (020-redis-caching-layer
follow-up — removes src/'s runtime dependency on backend being network-reachable).

Calls backend's own FastAPI app in-process via httpx's ASGITransport — no real socket opened,
no network dependency — while still going through the exact same router → Query()-default
resolution → cache_gateway.get_or_set() path a real browser request would take. This is the
key improvement over an earlier version of this module, which called each router's extracted
payload-builder service function directly and had to hardcode its own copy of every endpoint's
default query-parameter values (page, size, sort, ...) to compute a matching cache key — a
second place that could silently drift from the router's own Query(default=...) declarations.
Going through the ASGI app instead makes the router the single source of truth for what
"default" means; this module never encodes a default value of its own — it just omits query
params it doesn't want to customize, exactly like a browser's first request would.
"""
from httpx import ASGITransport, AsyncClient
import structlog

logger = structlog.get_logger()

_LANGUAGES = ("en", "zh-TW")
_REQUEST_TIMEOUT_SECONDS = 15


async def warm_default_reads(reason: str = "") -> None:
    from backend.main import app
    from backend.services.auth_service import create_guest_access_token

    headers = {"Authorization": f"Bearer {create_guest_access_token('cache-warmup')}"}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://cache-warmup.internal",
        timeout=_REQUEST_TIMEOUT_SECONDS,
    ) as client:
        topic_ids = await _active_topic_ids(client, headers)

        for topic_id in (None, *topic_ids):
            for lang in _LANGUAGES:
                params = {"lang": lang, **({"topic_id": topic_id} if topic_id else {})}
                await _safe_get(client, "/articles", params, headers, reason)
                await _safe_get(client, "/analyses/graph", params, headers, reason)
                if topic_id is not None:
                    await _safe_get(client, "/weekly-reports/latest", params, headers, reason)

            # tag-groups doesn't vary by lang (its own cache_gateway.get_or_set() call passes
            # no lang= at all), so it's warmed once per topic, outside the language loop.
            tag_params = {"topic_id": topic_id} if topic_id else {}
            await _safe_get(client, "/tag-groups", tag_params, headers, reason)

    logger.info("cache_warmup_completed", reason=reason, topics_warmed=len(topic_ids) + 1)


async def _active_topic_ids(client: AsyncClient, headers: dict) -> list:
    try:
        resp = await client.get("/topics", headers=headers)
        resp.raise_for_status()
        return [t["id"] for t in resp.json()]
    except Exception as e:
        logger.warning("cache_warmup_topic_lookup_failed", error=str(e))
        return []


async def _safe_get(client: AsyncClient, path: str, params: dict, headers: dict, reason: str) -> None:
    try:
        resp = await client.get(path, params=params, headers=headers)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("cache_warmup_target_failed", path=path, params=params, reason=reason, error=str(e))
