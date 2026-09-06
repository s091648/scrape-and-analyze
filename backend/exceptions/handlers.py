import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sentry_sdk import capture_exception

from shared.domain.exceptions import (
    DomainError,
    ValidationError,
    NotFoundError,
    ConflictError,
    UnauthorizedError,
    ForbiddenError,
    ExternalDependencyError,
)
from backend.schemas.error import ErrorResponse, ErrorBody

logger = structlog.get_logger()

# Ordered (category, status_code, error_code, generic_message). Checked most-specific
# category first via isinstance; the single place a new category's status code is
# registered (see spec FR-005).
_CATEGORY_MAPPING = [
    (ValidationError, 400, "VALIDATION_ERROR"),
    (UnauthorizedError, 401, "UNAUTHORIZED"),
    (ForbiddenError, 403, "FORBIDDEN"),
    (NotFoundError, 404, "NOT_FOUND"),
    (ConflictError, 409, "CONFLICT"),
    (ExternalDependencyError, 502, "EXTERNAL_DEPENDENCY_ERROR"),
]

# Categories whose response message MUST NOT echo the exception's own text
# (FR-009): unexpected/internal failures and confirmed external-dependency failures.
_SANITIZED_STATUS_CODES = {500, 502}

_GENERIC_MESSAGES = {
    500: "An unexpected error occurred",
    502: "An upstream dependency is unavailable",
}


def _request_id() -> str:
    return structlog.contextvars.get_contextvars().get("request_id", "unknown")


def _build_response(status_code: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, request_id=_request_id()))
    return JSONResponse(status_code=status_code, content=body.model_dump())


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    for category, status_code, code in _CATEGORY_MAPPING:
        if isinstance(exc, category):
            message = _GENERIC_MESSAGES[status_code] if status_code in _SANITIZED_STATUS_CODES else str(exc)
            if status_code in _SANITIZED_STATUS_CODES:
                capture_exception(exc)
                logger.error("domain_error", code=code, status_code=status_code, error=str(exc))
            else:
                # Expected/recoverable per exception-handling.md (400/401/403/404/409) — not
                # sent to Sentry and not counted in admin.requestErrorRate (5xx-only), but still
                # logged at warning so a spike (e.g. a real bug that happens to surface as 404s)
                # is discoverable via the Logs tab instead of leaving zero trace.
                logger.warning("domain_error", code=code, status_code=status_code, error=str(exc))
            return _build_response(status_code, code, message)

    # DomainError raised without a registered shared category — default fallback (FR-007).
    capture_exception(exc)
    logger.error("unmapped_domain_error", error=str(exc))
    return _build_response(500, "INTERNAL_ERROR", _GENERIC_MESSAGES[500])


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Safety net for exceptions that reached the API boundary without being translated
    # into a DomainError — a guideline-conformance gap to close, not the intended path.
    capture_exception(exc)
    logger.error("unhandled_exception", error=str(exc), exc_info=exc)
    return _build_response(500, "INTERNAL_ERROR", _GENERIC_MESSAGES[500])


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
