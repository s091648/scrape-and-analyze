SUPPORTED_LANGUAGES = [
    {"code": "en", "name": "English", "native_name": "English"},
    {"code": "zh-TW", "name": "Traditional Chinese", "native_name": "繁體中文"},
]


def resolve_language_from_ip(ip: str) -> str:
    try:
        from shared.utils.geoip import get_geo
        geo = get_geo(ip)
        country = geo.get("country", "")
        if country == "TW":
            return "zh-TW"
        return "en"
    except Exception:
        return "en"
