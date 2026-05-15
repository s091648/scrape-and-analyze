from unittest.mock import patch, MagicMock


def test_get_geo_returns_empty_dict_when_db_missing():
    """If the mmdb file does not exist, get_geo returns {} gracefully."""
    with patch("geoip2.database.Reader", side_effect=FileNotFoundError):
        # Force module re-init with missing file
        import importlib
        import shared.utils.geoip as geoip_mod
        geoip_mod._reader = None  # reset singleton
        with patch("os.path.exists", return_value=False):
            result = geoip_mod.get_geo("1.2.3.4")
    assert result == {}


def test_get_geo_returns_country_and_city():
    mock_reader = MagicMock()
    mock_city = MagicMock()
    mock_city.country.iso_code = "TW"
    mock_city.city.name = "Taipei"
    mock_reader.city.return_value = mock_city

    import shared.utils.geoip as geoip_mod
    original = geoip_mod._reader
    geoip_mod._reader = mock_reader
    try:
        result = geoip_mod.get_geo("203.74.12.1")
    finally:
        geoip_mod._reader = original

    assert result["country"] == "TW"
    assert result["city"] == "Taipei"


def test_get_geo_returns_empty_on_lookup_error():
    mock_reader = MagicMock()
    mock_reader.city.side_effect = Exception("address not found")

    import shared.utils.geoip as geoip_mod
    original = geoip_mod._reader
    geoip_mod._reader = mock_reader
    try:
        result = geoip_mod.get_geo("0.0.0.0")
    finally:
        geoip_mod._reader = original

    assert result == {}
