from fastapi import APIRouter, Request

from backend.schemas.language import LanguagesResponse

router = APIRouter()

SUPPORTED_LANGUAGES = [
    {"code": "en", "name": "English", "native_name": "English"},
    {"code": "zh-TW", "name": "Traditional Chinese", "native_name": "繁體中文"},
]


def resolve_language_from_ip(ip: str) -> str:
    """Resolve preferred language from IP using geoip."""
    try:
        from shared.utils.geoip import get_geo

        geo = get_geo(ip)
        country = geo.get("country", "")

        if country == "TW":
            return "zh-TW"
        return "en"
    except Exception:
        return "en"


@router.get("/languages", response_model=LanguagesResponse)
def get_languages(request: Request):
    """Get available languages and resolved language from client IP."""
    client_ip = None
    if request.client:
        client_ip = request.client.host

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    resolved = resolve_language_from_ip(client_ip) if client_ip else "en"

    return LanguagesResponse(
        available=SUPPORTED_LANGUAGES,
        resolved=resolved,
    )