from typing import Optional

from fastapi import Request


def get_client_origin(request: Request) -> Optional[str]:
    """First `X-Forwarded-For` hop, falling back to the ASGI-reported client host, or
    None if neither is available. Consolidates the identical logic previously
    duplicated in `backend/routers/languages.py`, `backend/routers/bootstrap.py`, and
    `backend/services/auth_service.py::compute_guest_id` (026-rate-limit-codegen
    research.md Decision 2) — callers that need a non-None key (e.g. a rate-limit
    counter) fall back with `get_client_origin(request) or "unknown"` themselves,
    same as `compute_guest_id` already did before this consolidation.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    first_hop = forwarded.split(",")[0].strip()
    if first_hop:
        return first_hop
    return request.client.host if request.client else None
