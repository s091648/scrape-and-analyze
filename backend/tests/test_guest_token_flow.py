"""Independent-test-style integration coverage for US2 (018-public-api-auth):
a caller with no account can obtain a guest token and use it against a
require_any_token-gated route, proven in isolation via a throwaway test route
(same pattern as test_exception_handlers.py's /__test/raise/{category})."""
import os

import pytest
from fastapi import Depends
from starlette.testclient import TestClient

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret")


@pytest.fixture
def client():
    from backend.main import app
    from backend.auth.guards import require_any_token

    @app.get("/__test/guest-gated")
    def _gated(payload: dict = Depends(require_any_token)):
        return {"tier": payload.get("tier", "user")}

    return TestClient(app, raise_server_exceptions=False)


def test_full_round_trip_guest_token_grants_access(client):
    pair = client.post("/auth/guest").json()
    response = client.get(
        "/__test/guest-gated",
        headers={"Authorization": f"Bearer {pair['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["tier"] == "guest"


def test_no_token_is_rejected(client):
    response = client.get("/__test/guest-gated")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_refresh_token_is_rejected_as_access(client):
    pair = client.post("/auth/guest").json()
    response = client.get(
        "/__test/guest-gated",
        headers={"Authorization": f"Bearer {pair['refresh_token']}"},
    )
    assert response.status_code == 401
