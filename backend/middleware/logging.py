import os
import uuid
import time
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()

_SECRET = os.environ.get("NEXTAUTH_SECRET", "")


def _extract_user(request: Request) -> dict:
    """Decode JWT from Authorization header. Returns {"user_id": "anonymous"} for unauthenticated requests."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return {"user_id": "anonymous"}
    token = auth.split(" ", 1)[1]
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


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        # User identity from JWT
        user_info = _extract_user(request)

        # Real IP (corrected by ProxyHeadersMiddleware upstream)
        ip = request.client.host if request.client else None

        # Geo-IP
        geo: dict = {}
        if ip:
            try:
                from src.observability.geoip import get_geo
                geo = get_geo(ip)
            except Exception:
                pass

        log_fields = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            **user_info,
            **({"ip": ip} if ip else {}),
            **(({"user_agent": request.headers.get("user-agent")} if request.headers.get("user-agent") else {})),
            **({"geo_country": geo["country"]} if geo.get("country") else {}),
            **({"geo_city": geo["city"]} if geo.get("city") else {}),
        }

        logger.info("request", **log_fields)

        response.headers["X-Request-ID"] = request_id
        return response
