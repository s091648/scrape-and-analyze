"""US3 (018-public-api-auth): existing logged-in users and admins are unaffected by
this feature — no re-authentication, no new prompt, no role-logic change. Verifies a
real user token and a real admin token succeed unchanged on both the newly-gated
endpoints (previously fully public) and the endpoints that already required a role
before this feature existed."""
import os
import time
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret")
SECRET = os.environ["NEXTAUTH_SECRET"]


def _token(role, sub="user-1"):
    from jose import jwt
    return jwt.encode(
        {"sub": sub, "role": role, "exp": int(time.time()) + 3600},
        SECRET, algorithm="HS256",
    )


@pytest.fixture
def client():
    from backend.main import app
    from backend.database import get_db

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = None
    mock_db.query.return_value.filter.return_value.first.return_value = None

    def override():
        yield mock_db

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.parametrize("path", ["/articles", "/topics", "/languages"])
def test_real_user_token_succeeds_on_newly_gated_endpoints(client, path):
    response = client.get(path, headers={"Authorization": f"Bearer {_token('user')}"})
    assert response.status_code != 401


@pytest.mark.parametrize("path", ["/articles", "/topics", "/languages"])
def test_real_admin_token_succeeds_on_newly_gated_endpoints(client, path):
    response = client.get(path, headers={"Authorization": f"Bearer {_token('admin')}"})
    assert response.status_code != 401


def test_admin_only_endpoints_still_require_admin_role_unchanged(client):
    # A real (non-admin) user token must still be refused on an already-admin-only
    # endpoint — this feature must not have loosened that check.
    response = client.get(
        f"/scraper-settings",
        headers={"Authorization": f"Bearer {_token('user')}"},
    )
    assert response.status_code == 403


def test_admin_token_still_succeeds_on_pre_existing_admin_endpoint(client):
    response = client.get(
        "/scraper-settings",
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )
    assert response.status_code != 401
    assert response.status_code != 403
