from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_responses(*status_codes: int) -> dict:
    """OpenAPI `responses=` fragment for status codes an endpoint can produce via
    the central exception handler (backend/exceptions/handlers.py)."""
    return {code: {"model": ErrorResponse} for code in status_codes}
