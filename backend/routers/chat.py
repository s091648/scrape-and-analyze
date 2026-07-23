from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from opentelemetry import trace as _otel_trace

from backend.auth.guards import require_any_token
from backend.config import REDIS_URL
from backend.schemas.error import error_responses
from backend.services.chat_service import (
    DAILY_LIMIT_GUEST,
    DAILY_LIMIT_USER,
    ChatCompletionService,
    ChatIdentity,
    RateLimitExceeded,
    RateLimitService,
)

logger = structlog.get_logger()
router = APIRouter(tags=["chat"])


def _make_redis():
    import redis.asyncio as aioredis
    return aioredis.from_url(REDIS_URL)


def _identity_from_payload(payload: dict) -> ChatIdentity:
    """Map an already-verified require_any_token payload to a ChatIdentity. The
    guest_id claim (research.md §7, 018-public-api-auth) replaces the retired
    __rag_gid cookie / ip-hash logic — the guest token itself is the identity now."""
    if payload.get("tier") == "guest":
        return ChatIdentity(tier="guest", guest_id=payload.get("guest_id"))
    role = payload.get("role", "user")
    user_id = payload.get("sub")
    if role == "admin":
        return ChatIdentity(tier="admin", user_id=user_id)
    return ChatIdentity(tier="user", user_id=user_id)


@router.post("/chat/completions", responses=error_responses(401))
async def chat_completions(
    request: Request,
    x_topic_id: Optional[str] = Header(default=None),
    x_pinned_article_ids: Optional[str] = Header(default=None),
    payload: dict = Depends(require_any_token),
):
    span = _otel_trace.get_current_span()
    span.set_attribute("chat.topic_id", x_topic_id or "")

    body = await request.json()
    messages = body.get("messages", [])

    identity = _identity_from_payload(payload)

    span.set_attribute("chat.identity_tier", identity.tier)

    redis_client = _make_redis()
    remaining = -1
    limit = -1
    try:
        rate_svc = RateLimitService(redis_client)
        remaining, limit = await rate_svc.check_rate_limit(identity)
    except RateLimitExceeded as exc:
        tier_label = "訪客" if identity.tier == "guest" else "用戶"
        raise HTTPException(
            status_code=429,
            detail={
                "detail": f"每日問答次數已達上限（{tier_label}：{exc.limit}次/天）",
                "limit": exc.limit,
            },
        ) from exc
    finally:
        await redis_client.aclose()

    span.set_attribute("chat.rate_limit_remaining", remaining)
    span.set_attribute("chat.rate_limit_limit", limit)
    logger.info(
        "chat_request",
        tier=identity.tier,
        remaining=remaining,
        limit=limit,
        topic_id=x_topic_id,
    )

    pinned_ids = [pid.strip() for pid in x_pinned_article_ids.split(",") if pid.strip()] if x_pinned_article_ids else None
    completion_svc = ChatCompletionService()

    async def generate():
        try:
            async for chunk in completion_svc.stream_completions(messages, x_topic_id, pinned_ids):
                yield chunk
        except Exception:
            # The HTTP status (200) is already committed once streaming starts, so a
            # mid-stream failure — including all LLM providers being exhausted — can't
            # be expressed as a status code. It's signaled in-band using the same
            # error.code/error.message vocabulary as the ErrorResponse contract instead
            # (contracts/error-response.md "Streaming exception" clause).
            logger.exception("chat_stream_failed", tier=identity.tier)
            yield b'data: {"error": {"code": "EXTERNAL_DEPENDENCY_ERROR", "message": "An upstream dependency is unavailable"}}\n\n'
            yield b"data: [DONE]\n\n"

    response = StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Limit": str(limit),
        },
    )
    return response


@router.get("/chat/quota", responses=error_responses(401))
async def chat_quota(payload: dict = Depends(require_any_token)):
    identity = _identity_from_payload(payload)

    redis_client = _make_redis()
    try:
        rate_svc = RateLimitService(redis_client)
        remaining, limit = await rate_svc.get_quota(identity)
    finally:
        await redis_client.aclose()

    return JSONResponse({
        "tier": identity.tier,
        "remaining": remaining,
        "limit": limit,
        "guest_daily_limit": DAILY_LIMIT_GUEST,
        "member_daily_limit": DAILY_LIMIT_USER,
    })
