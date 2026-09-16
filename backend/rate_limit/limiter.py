import structlog
import redis.asyncio as aioredis
from fastapi import Depends, Request

from backend.auth.guards import require_any_token
from backend.config import REDIS_URL
from backend.rate_limit.client_origin import get_client_origin
from backend.rate_limit.policies import RateLimitPolicy, GUEST_TOKEN, AUTH_ATTEMPT, CHAT_BURST, SEARCH
from shared.domain.exceptions import RateLimitExceededError

logger = structlog.get_logger()


def _make_redis():
    return aioredis.from_url(REDIS_URL)


def _identity_key(payload: dict) -> str:
    """Mirrors chat.py's _identity_from_payload/ChatIdentity split (rate:user:*/
    rate:guest:* key shape) so a guest_id string and a user UUID can never collide."""
    if payload.get("tier") == "guest":
        return f"guest:{payload.get('guest_id')}"
    return f"user:{payload.get('sub')}"


def _is_admin(payload: dict) -> bool:
    return payload.get("tier") != "guest" and payload.get("role") == "admin"


async def _check_policy(policy: RateLimitPolicy, key_suffix: str) -> None:
    key = f"ratelimit:{policy.name}:{key_suffix}"
    redis_client = _make_redis()
    try:
        try:
            count = await redis_client.incr(key)
            if count == 1:
                await redis_client.expire(key, policy.window_seconds)
        except Exception:
            # Fail open (research.md Decision 5): a Redis blip must not take down every
            # rate-limited endpoint. Observability principle: fail silently with a no-op
            # fallback, but still log the failure so it's discoverable, not swallowed.
            logger.warning("rate_limit_check_failed_open", policy=policy.name)
            return

        if count > policy.max_requests:
            try:
                ttl = await redis_client.ttl(key)
            except Exception:
                ttl = None
            retry_after_seconds = ttl if ttl and ttl > 0 else policy.window_seconds
            logger.warning(
                "rate_limit_exceeded",
                policy=policy.name,
                count=count,
                limit=policy.max_requests,
                retry_after_seconds=retry_after_seconds,
            )
            raise RateLimitExceededError(
                f"Rate limit exceeded for {policy.name}",
                retry_after_seconds=retry_after_seconds,
            )
    finally:
        await redis_client.aclose()


async def guest_token_limit(request: Request) -> None:
    origin = get_client_origin(request) or "unknown"
    await _check_policy(GUEST_TOKEN, origin)


async def auth_attempt_limit(request: Request) -> None:
    origin = get_client_origin(request) or "unknown"
    await _check_policy(AUTH_ATTEMPT, origin)


async def chat_burst_limit(payload: dict = Depends(require_any_token)) -> None:
    # Admin already bypasses chat's daily quota entirely (chat_service.py::
    # RateLimitService.check_rate_limit) — mirror that here so the same endpoint
    # doesn't start enforcing a burst limit against admin that its daily quota exempts.
    if _is_admin(payload):
        return
    await _check_policy(CHAT_BURST, _identity_key(payload))


async def search_limit(payload: dict = Depends(require_any_token)) -> None:
    await _check_policy(SEARCH, _identity_key(payload))
