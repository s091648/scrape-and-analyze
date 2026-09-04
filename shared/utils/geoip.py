"""
GeoIP lookup — optional MaxMind GeoLite2 adapter.
Used by the backend request-logging middleware.
"""
import os

_DB_PATH: str | None = None
_reader = None


def configure(db_path: str) -> None:
    """Must be called once at service startup with the db path from the calling
    service's own centralized config (e.g. backend/config.py's GEOIP_DB_PATH) —
    shared/ utility code must not read the environment itself (025-iac-provisioning
    US5, FR-017)."""
    global _DB_PATH, _reader
    _DB_PATH = db_path
    _reader = None  # force re-init against the new path on next lookup


def _init_reader():
    global _reader
    if _reader is not None:
        return _reader
    if not _DB_PATH or not os.path.exists(_DB_PATH):
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
