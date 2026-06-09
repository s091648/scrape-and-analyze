from fastapi import APIRouter, Request

from backend.schemas.language import LanguagesResponse
from backend.services.language_service import SUPPORTED_LANGUAGES, resolve_language_from_ip

router = APIRouter()


@router.get("/languages", response_model=LanguagesResponse)
def get_languages(request: Request):
    client_ip = None
    if request.client:
        client_ip = request.client.host

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    resolved = resolve_language_from_ip(client_ip) if client_ip else "en"

    return LanguagesResponse(available=SUPPORTED_LANGUAGES, resolved=resolved)
