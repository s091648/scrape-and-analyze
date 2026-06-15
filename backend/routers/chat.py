import hashlib
import os
import time
import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Cookie, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from jose import JWTError, jwt
from opentelemetry import trace as _otel_trace

from backend.services.chat_service import (
    DAILY_LIMIT_GUEST,
    DAILY_LIMIT_USER,
    ChatIdentity,
    ChatService,
    RateLimitExceeded,
)

logger = structlog.get_logger()
router = APIRouter()


def _make_redis():
    import redis.asyncio as aioredis
    redis_url = os.environ.get("REDIS_URL") or "redis://redis:6379/0"
    return aioredis.from_url(redis_url)


def _parse_identity(authorization: Optional[str]) -> Optional[ChatIdentity]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ")
    secret = os.environ.get("NEXTAUTH_SECRET", "")
    try:
        payload = jwt.decode(
            token, secret, algorithms=["HS256"], options={"verify_exp": False}
        )
        if payload.get("exp", 0) < int(time.time()):
            return None
        role = payload.get("role", "user")
        user_id = payload.get("sub")
        if role == "admin":
            return ChatIdentity(tier="admin", user_id=user_id)
        return ChatIdentity(tier="user", user_id=user_id)
    except JWTError:
        return None


def _guest_identity(
    request: Request, cookie_value: Optional[str]
) -> tuple[ChatIdentity, Optional[str]]:
    """Returns (identity, new_cookie_value_to_set_on_response)."""
    if cookie_value:
        return ChatIdentity(tier="guest", guest_id=cookie_value), None

    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    ua = request.headers.get("user-agent", "")
    ip_hash = hashlib.sha256(f"{client_ip}{ua}".encode()).hexdigest()[:16]
    new_cookie = str(uuid.uuid4())
    return ChatIdentity(tier="guest", guest_id=f"ip:{ip_hash}"), new_cookie


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_topic_id: Optional[str] = Header(default=None),
    rag_gid: Optional[str] = Cookie(alias="__rag_gid", default=None),
):
    span = _otel_trace.get_current_span()
    span.set_attribute("chat.topic_id", x_topic_id or "")

    body = await request.json()
    messages = body.get("messages", [])

    identity = _parse_identity(authorization)
    new_cookie: Optional[str] = None
    if identity is None:
        identity, new_cookie = _guest_identity(request, rag_gid)

    span.set_attribute("chat.identity_tier", identity.tier)

    redis_client = _make_redis()
    remaining = -1
    limit = -1
    try:
        service = ChatService(redis_client)
        remaining, limit = await service.check_rate_limit(identity)
    except RateLimitExceeded as exc:
        tier_label = "訪客" if identity.tier == "guest" else "用戶"
        raise HTTPException(
            status_code=429,
            detail={
                "detail": f"每日問答次數已達上限（{tier_label}：{exc.limit}次/天）",
                "limit": exc.limit,
            },
        )
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

    async def generate():
        svc = ChatService()
        try:
            async for chunk in svc.stream_completions(messages, x_topic_id):
                yield chunk
        except Exception:
            logger.exception("chat_stream_failed", tier=identity.tier)
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
    if new_cookie:
        response.set_cookie(
            "__rag_gid",
            new_cookie,
            httponly=True,
            samesite="lax",
            max_age=31536000,
            path="/",
        )
    return response


@router.get("/chat/quota")
async def chat_quota(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    rag_gid: Optional[str] = Cookie(alias="__rag_gid", default=None),
):
    identity = _parse_identity(authorization)
    new_cookie: Optional[str] = None
    if identity is None:
        identity, new_cookie = _guest_identity(request, rag_gid)

    redis_client = _make_redis()
    try:
        service = ChatService(redis_client)
        remaining, limit = await service.get_quota(identity)
    finally:
        await redis_client.aclose()

    response = JSONResponse({
        "tier": identity.tier,
        "remaining": remaining,
        "limit": limit,
        "guest_daily_limit": DAILY_LIMIT_GUEST,
        "member_daily_limit": DAILY_LIMIT_USER,
    })
    if new_cookie:
        response.set_cookie(
            "__rag_gid",
            new_cookie,
            httponly=True,
            samesite="lax",
            max_age=31536000,
            path="/",
        )
    return response
