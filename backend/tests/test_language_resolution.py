"""Tests for GeoIP-based language resolution in the languages router."""
from unittest.mock import patch


def test_resolve_language_returns_zh_tw_for_taiwan():
    """When GeoIP returns country=TW, resolve_language_from_ip returns zh-TW."""
    with patch("src.infrastructure.shared.observability.geoip.get_geo", return_value={"country": "TW", "city": "Taipei"}):
        from backend.routers.languages import resolve_language_from_ip
        result = resolve_language_from_ip("203.74.12.1")
    assert result == "zh-TW"


def test_resolve_language_returns_en_for_other_countries():
    """When GeoIP returns a non-TW country, resolve_language_from_ip returns en."""
    with patch("src.infrastructure.shared.observability.geoip.get_geo", return_value={"country": "US", "city": "New York"}):
        from backend.routers.languages import resolve_language_from_ip
        result = resolve_language_from_ip("8.8.8.8")
    assert result == "en"


def test_resolve_language_defaults_to_en_on_geoip_failure():
    """When GeoIP returns empty dict, resolve_language_from_ip defaults to en."""
    with patch("src.infrastructure.shared.observability.geoip.get_geo", return_value={}):
        from backend.routers.languages import resolve_language_from_ip
        result = resolve_language_from_ip("1.2.3.4")
    assert result == "en"


def test_resolve_language_defaults_to_en_on_exception():
    """When GeoIP raises an exception, resolve_language_from_ip defaults to en."""
    with patch("src.infrastructure.shared.observability.geoip.get_geo", side_effect=RuntimeError("db error")):
        from backend.routers.languages import resolve_language_from_ip
        result = resolve_language_from_ip("1.2.3.4")
    assert result == "en"
