import os
from dataclasses import dataclass
from datetime import date
from typing import AsyncIterator, Optional

import httpx
import structlog

logger = structlog.get_logger()

DAILY_LIMIT_USER = 50
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


class ChatService:
    def __init__(self, redis_client=None) -> None:
        self._redis = redis_client
        self._chat_service_url = os.environ.get("CHAT_SERVICE_URL", "").rstrip("/")
        self._chat_service_api_key = os.environ.get("CHAT_SERVICE_API_KEY", "")

    async def check_rate_limit(self, identity: ChatIdentity) -> tuple[int, int]:
        """Check and increment rate limit counter. Returns (remaining, limit). remaining=-1 means unlimited."""
        if identity.tier == "admin":
            return -1, -1

        today = date.today().isoformat()
        if identity.tier == "user":
            key = f"rate:user:{identity.user_id}:{today}"
            limit = DAILY_LIMIT_USER
        else:
            key = f"rate:guest:{identity.guest_id}:{today}"
            limit = DAILY_LIMIT_GUEST

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

        today = date.today().isoformat()
        if identity.tier == "user":
            key = f"rate:user:{identity.user_id}:{today}"
            limit = DAILY_LIMIT_USER
        else:
            key = f"rate:guest:{identity.guest_id}:{today}"
            limit = DAILY_LIMIT_GUEST

        count_raw = await self._redis.get(key)
        count = int(count_raw) if count_raw else 0
        return max(0, limit - count), limit

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
