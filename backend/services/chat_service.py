import os
from dataclasses import dataclass
from datetime import date
from typing import AsyncIterator, Optional

import httpx
import structlog

logger = structlog.get_logger()

DAILY_LIMIT_USER = 10
DAILY_LIMIT_GUEST = 3


class RateLimitExceeded(Exception):
    def __init__(self, limit: int) -> None:
        self.limit = limit
        super().__init__(f"Rate limit exceeded: {limit}/day")


@dataclass
class ChatIdentity:
    tier: str  # "admin", "user", "guest"
    user_id: Optional[str] = None
    guest_id: Optional[str] = None  # cookie UUID or "ip:{hash}"


class RateLimitService:
    """Redis-backed daily quota tracker. Owns the Redis connection for its lifetime."""

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    def _key_and_limit(self, identity: ChatIdentity) -> tuple[str, int]:
        today = date.today().isoformat()
        if identity.tier == "user":
            return f"rate:user:{identity.user_id}:{today}", DAILY_LIMIT_USER
        return f"rate:guest:{identity.guest_id}:{today}", DAILY_LIMIT_GUEST

    async def check_rate_limit(self, identity: ChatIdentity) -> tuple[int, int]:
        """Increment counter and return (remaining, limit). remaining=-1 means unlimited."""
        if identity.tier == "admin":
            return -1, -1

        key, limit = self._key_and_limit(identity)
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, 86400)

        logger.info(
            "chat_rate_limit_check",
            identity_tier=identity.tier,
            rate_limit_counter=count,
            limit=limit,
            key=key,
        )

        if count > limit:
            raise RateLimitExceeded(limit=limit)

        return limit - count, limit

    async def get_quota(self, identity: ChatIdentity) -> tuple[int, int]:
        """Read current quota without consuming a request. Returns (remaining, limit). -1 means unlimited."""
        if identity.tier == "admin":
            return -1, -1

        key, limit = self._key_and_limit(identity)
        count_raw = await self._redis.get(key)
        count = int(count_raw) if count_raw else 0
        return max(0, limit - count), limit


class ChatCompletionService:
    """Stateless httpx proxy to the downstream LLM chat service. No Redis dependency."""

    def __init__(self) -> None:
        self._chat_service_url = os.environ.get("CHAT_SERVICE_URL", "").rstrip("/")
        self._chat_service_api_key = os.environ.get("CHAT_SERVICE_API_KEY", "")

    async def stream_completions(
        self, messages: list, topic_id: Optional[str] = None
    ) -> AsyncIterator[bytes]:
        body: dict = {"messages": messages, "stream": True}
        if topic_id:
            body["topic_id"] = topic_id

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._chat_service_api_key}",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self._chat_service_url}/v1/chat/completions",
                json=body,
                headers=headers,
            ) as response:
                logger.info(
                    "chat_service_response",
                    chat_service_status=response.status_code,
                    topic_id=topic_id,
                )
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk
