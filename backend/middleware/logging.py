import json
import uuid
import time
import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.config import NEXTAUTH_SECRET

logger = structlog.get_logger()

_SECRET = NEXTAUTH_SECRET

# Logged bodies are capped well below Loki's per-line ingestion limits — this is for
# debugging typical JSON payloads, not for reconstructing large uploads.
_MAX_BODY_LOG_BYTES = 4096

# Substring match (not exact key) so variants like current_password/new_password/
# refresh_token/api_key_env are all caught without enumerating every schema field.
_SENSITIVE_KEY_SUBSTRINGS = ("password", "token", "secret", "api_key", "apikey")


def _redact(value):
    if isinstance(value, dict):
        return {
            k: ("***" if any(s in k.lower() for s in _SENSITIVE_KEY_SUBSTRINGS) else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _extract_user(auth_header: str) -> dict:
    """Decode JWT from the raw Authorization header value. Returns {"user_id": "anonymous",
    "user_role": "guest"} for unauthenticated requests, and "guest" also covers a guest access
    token (its claims carry "tier", never "role" — see auth_service.py's _create_guest_token).
    user_role is always set (never omitted) so LogQL `sum by (user_role)` never lumps guest
    traffic into an unlabeled/empty group — see admin.requestsByRoleChart in
    frontend/app/admin/monitoring/monitoring-content.tsx."""
    if not auth_header.lower().startswith("bearer "):
        return {"user_id": "anonymous", "user_role": "guest"}
    token = auth_header.split(" ", 1)[1]
    try:
        from jose import jwt as jose_jwt
        payload = jose_jwt.decode(
            token, _SECRET, algorithms=["HS256"],
            options={"verify_aud": False},
        )
        user: dict = {
            "user_id": payload.get("sub", "anonymous"),
            "user_role": payload.get("role") or "guest",
        }
        if payload.get("email"):
            user["user_email"] = payload["email"]
        return user
    except Exception:
        return {"user_id": "anonymous", "user_role": "guest"}


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

        # Wiretaps the request body as it streams past — forwards every message to the
        # downstream app untouched (same "no buffering of its own" principle as
        # send_wrapper above), just also accumulates chunks up to _MAX_BODY_LOG_BYTES so
        # they can be logged after the request completes.
        body_chunks: list[bytes] = []
        body_truncated = False

        async def receive_wrapper() -> Message:
            nonlocal body_truncated
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                if chunk and not body_truncated:
                    if sum(len(c) for c in body_chunks) + len(chunk) <= _MAX_BODY_LOG_BYTES:
                        body_chunks.append(chunk)
                    else:
                        body_truncated = True
            return message

        await self.app(scope, receive_wrapper, send_wrapper)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        # Railway/Docker healthchecks poll GET /health every few seconds (see docker-compose.yml
        # and the platform's own health-probe config) — logging every one at INFO would flood the
        # backend's log stream with a line that carries no signal. FastAPIInstrumentor already
        # excludes this same path from tracing (excluded_urls="health" in backend/main.py) for the
        # same reason. A failing health check (DB down, non-2xx) is still worth keeping.
        if scope["path"] == "/health" and status_code < 400:
            return

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

        query_params = (scope.get("query_string") or b"").decode("latin-1")

        # Only decoded when the body looks like a small JSON payload — multipart/form-data
        # (file uploads) and anything that overflowed _MAX_BODY_LOG_BYTES stays unlogged,
        # since neither is meaningful (or safe, size-wise) to ship to Loki as a single field.
        payload = None
        if body_chunks and not body_truncated:
            content_type = raw_headers.get(b"content-type", b"").decode("latin-1")
            if "application/json" in content_type:
                try:
                    parsed = json.loads(b"".join(body_chunks))
                    payload = json.dumps(_redact(parsed), ensure_ascii=False)
                except Exception:
                    pass

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
            **({"query_params": query_params} if query_params else {}),
            **({"payload": payload} if payload is not None else {}),
        }

        logger.info("request", **log_fields)
