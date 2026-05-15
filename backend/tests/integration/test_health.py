"""
Integration test for /health.

Unit test mocks check_db_connection.  This test exercises a real SELECT 1.
"""
import pytest

pytestmark = pytest.mark.integration


def test_health_with_real_db(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"
