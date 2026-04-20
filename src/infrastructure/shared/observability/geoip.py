"""
GeoIP lookup — optional MaxMind GeoLite2 adapter.
Used by the backend request-logging middleware.
"""
import os
from typing import Optional

_DB_PATH = os.environ.get("GEOIP_DB_PATH", "/app/data/GeoLite2-City.mmdb")
_reader = None


def _init_reader():
    global _reader
    if _reader is not None:
        return _reader
    if not os.path.exists(_DB_PATH):
        return None
    try:
        import geoip2.database
        _reader = geoip2.database.Reader(_DB_PATH)
    except Exception:
        pass
    return _reader


def get_geo(ip: str) -> dict:
    """Return {"country": "TW", "city": "Taipei"} or {} on any failure."""
    reader = _init_reader()
    if reader is None:
        return {}
    try:
        response = reader.city(ip)
        result = {}
        if response.country.iso_code:
            result["country"] = response.country.iso_code
        if response.city.name:
            result["city"] = response.city.name
        return result
    except Exception:
        return {}
