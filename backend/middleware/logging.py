import uuid
import time
import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.config import NEXTAUTH_SECRET

logger = structlog.get_logger()

_SECRET = NEXTAUTH_SECRET


def _extract_user(auth_header: str) -> dict:
    """Decode JWT from the raw Authorization header value. Returns {"user_id": "anonymous"} for
    unauthenticated requests."""
    if not auth_header.lower().startswith("bearer "):
        return {"user_id": "anonymous"}
    token = auth_header.split(" ", 1)[1]
    try:
        from jose import jwt as jose_jwt
        payload = jose_jwt.decode(
            token, _SECRET, algorithms=["HS256"],
            options={"verify_aud": False},
        )
        user: dict = {"user_id": payload.get("sub", "anonymous")}
        if payload.get("email"):
            user["user_email"] = payload["email"]
        if payload.get("role"):
            user["user_role"] = payload["role"]
        return user
    except Exception:
        return {"user_id": "anonymous"}


class RequestLoggingMiddleware:
    """Pure ASGI middleware — deliberately NOT a starlette.middleware.base.BaseHTTPMiddleware
    subclass. BaseHTTPMiddleware relays the downstream response through an internal buffer so it
    can hand dispatch() a single Response object to inspect/mutate; for a StreamingResponse (see
    /chat/completions) that collapses true chunk-by-chunk delivery into one burst sent only once
    the whole generation has finished, instead of the client watching tokens arrive live. Wrapping
    `send` directly here forwards every ASGI message untouched and adds no buffering of its own."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        raw_headers: dict[bytes, bytes] = dict(scope.get("headers") or [])
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        # User identity from JWT
        auth_header = raw_headers.get(b"authorization", b"").decode("latin-1")
        user_info = _extract_user(auth_header)

        # Real IP (corrected by ProxyHeadersMiddleware upstream)
        client = scope.get("client")
        ip = client[0] if client else None

        # Geo-IP
        geo: dict = {}
        if ip:
            try:
                from shared.utils.geoip import get_geo
                geo = get_geo(ip)
            except Exception:
                pass

        user_agent_bytes = raw_headers.get(b"user-agent")

        log_fields = {
            "method": scope["method"],
            "path": scope["path"],
            "status_code": status_code,
            "duration_ms": duration_ms,
            **user_info,
            **({"ip": ip} if ip else {}),
            **({"user_agent": user_agent_bytes.decode("latin-1")} if user_agent_bytes else {}),
            **({"geo_country": geo["country"]} if geo.get("country") else {}),
            **({"geo_city": geo["city"]} if geo.get("city") else {}),
        }

        logger.info("request", **log_fields)
