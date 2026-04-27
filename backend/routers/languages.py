from typing import List
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel

router = APIRouter()


# Supported languages configuration
SUPPORTED_LANGUAGES = [
    {"code": "en", "name": "English", "native_name": "English"},
    {"code": "zh-TW", "name": "Traditional Chinese", "native_name": "繁體中文"},
]


class LanguageInfo(BaseModel):
    code: str
    name: str
    native_name: str


class LanguagesResponse(BaseModel):
    available: List[LanguageInfo]
    resolved: str


def resolve_language_from_ip(ip: str) -> str:
    """Resolve preferred language from IP using geoip."""
    # Import here to avoid circular imports
    try:
        from src.infrastructure.shared.observability.geoip import get_geo

        geo = get_geo(ip)
        country = geo.get("country", "")

        # Map country to language
        if country == "TW":
            return "zh-TW"
        # Can add more mappings: CN -> zh-CN, JP -> ja, KR -> ko, etc.
        return "en"
    except Exception:
        return "en"


@router.get("/languages", response_model=LanguagesResponse)
def get_languages(request: Request):
    """Get available languages and resolved language from client IP."""
    # Get client IP
    client_ip = None
    if request.client:
        client_ip = request.client.host

    # Check for forwarded header (when behind proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    # Resolve language from IP
    resolved = resolve_language_from_ip(client_ip) if client_ip else "en"

    return LanguagesResponse(
        available=SUPPORTED_LANGUAGES,
        resolved=resolved,
    )