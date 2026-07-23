from fastapi import APIRouter, Depends, Request

from backend.auth.guards import require_any_token
from backend.schemas.error import error_responses
from backend.schemas.language import LanguagesResponse
from backend.services.language_service import SUPPORTED_LANGUAGES, resolve_language_from_ip

router = APIRouter(tags=["languages"])


@router.get("/languages", response_model=LanguagesResponse, responses=error_responses(401))
def get_languages(request: Request, _token: dict = Depends(require_any_token)):
    client_ip = None
    if request.client:
        client_ip = request.client.host

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    resolved = resolve_language_from_ip(client_ip) if client_ip else "en"

    return LanguagesResponse(available=SUPPORTED_LANGUAGES, resolved=resolved)
