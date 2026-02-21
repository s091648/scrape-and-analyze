import re
from fastapi.testclient import TestClient
from unittest.mock import patch


def test_request_id_header_present():
    from backend.main import app
    client = TestClient(app)
    with patch("backend.main.check_db_connection", return_value=True):
        response = client.get("/health")
    assert "x-request-id" in response.headers
    # Must be a valid UUID format
    assert re.match(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        response.headers["x-request-id"]
    )
