import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret")


def test_get_languages_returns_available_list():
    from backend.main import app

    client = TestClient(app)
    response = client.get("/languages")

    assert response.status_code == 200
    data = response.json()
    assert "available" in data
    assert "resolved" in data
    codes = [lang["code"] for lang in data["available"]]
    assert "en" in codes
    assert "zh-TW" in codes


def test_get_languages_no_ip_resolves_en():
    from backend.main import app

    client = TestClient(app)
    with patch("backend.routers.languages.resolve_language_from_ip", return_value="en"):
        response = client.get("/languages")

    assert response.status_code == 200
    assert response.json()["resolved"] == "en"


def test_get_languages_forwarded_for_header_is_used():
    from backend.main import app

    client = TestClient(app)
    with patch("backend.routers.languages.resolve_language_from_ip", return_value="zh-TW") as mock_resolve:
        response = client.get(
            "/languages",
            headers={"X-Forwarded-For": "1.2.3.4, 10.0.0.1"},
        )

    assert response.status_code == 200
    # The router extracts the first IP from the header
    mock_resolve.assert_called_once_with("1.2.3.4")


def test_get_languages_tw_ip_resolves_zh_tw():
    from backend.main import app

    client = TestClient(app)
    with patch("backend.routers.languages.resolve_language_from_ip", return_value="zh-TW"):
        response = client.get(
            "/languages",
            headers={"X-Forwarded-For": "111.248.0.1"},
        )

    assert response.status_code == 200
    assert response.json()["resolved"] == "zh-TW"


def test_get_languages_geoip_exception_falls_back_to_en():
    from backend.services.language_service import resolve_language_from_ip

    with patch("shared.utils.geoip.get_geo", side_effect=Exception("db missing")):
        result = resolve_language_from_ip("1.2.3.4")

    assert result == "en"
