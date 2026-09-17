from typing import Optional

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    # Only set for RATE_LIMIT_EXCEEDED (026-rate-limit-codegen) — every other error
    # category leaves this unset, and _build_response's exclude_none=True dump keeps
    # it out of those responses' JSON entirely, preserving the existing {code, message,
    # request_id} contract for them.
    retry_after_seconds: Optional[int] = None


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_responses(*status_codes: int) -> dict:
    """OpenAPI `responses=` fragment for status codes an endpoint can produce via
    the central exception handler (backend/exceptions/handlers.py)."""
    return {code: {"model": ErrorResponse} for code in status_codes}
