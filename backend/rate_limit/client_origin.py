from typing import Optional

from fastapi import Request

from backend.config import TRUSTED_PROXY_HOPS


def get_client_origin(request: Request) -> Optional[str]:
    """The client address trusted for rate-limiting/GeoIP/guest-id purposes, or None
    if unavailable. Consolidates the identical logic previously duplicated in
    `backend/routers/languages.py`, `backend/routers/bootstrap.py`, and
    `backend/services/auth_service.py::compute_guest_id` (026-rate-limit-codegen
    research.md Decision 2) — callers that need a non-None key (e.g. a rate-limit
    counter) fall back with `get_client_origin(request) or "unknown"` themselves,
    same as `compute_guest_id` already did before this consolidation.

    Only the *last* TRUSTED_PROXY_HOPS entries of `X-Forwarded-For` are ever
    trusted, read from the right: every hop except the ones appended by our own
    reverse proxies is client-supplied and trivially spoofable, so trusting the
    first (leftmost) hop — as this helper used to — let a caller set an arbitrary
    origin there and bypass origin-keyed rate limits entirely (CodeRabbit review,
    026-rate-limit-codegen PR #127). TRUSTED_PROXY_HOPS=1 (Railway's edge, the only
    proxy in front of this service in every deployed environment) means "trust the
    last entry"; TRUSTED_PROXY_HOPS=0 ignores the header altogether.
    """
    if TRUSTED_PROXY_HOPS > 0:
        forwarded = request.headers.get("x-forwarded-for", "")
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if len(hops) >= TRUSTED_PROXY_HOPS:
            return hops[-TRUSTED_PROXY_HOPS]
    return request.client.host if request.client else None
