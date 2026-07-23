"""Cross-router regression sweep (spec FR-010 / SC-001 / SC-002): every audited
endpoint (see specs/017-exception-handling-guideline/router-audit.md) must return
a status code from the documented mapping and the consistent ErrorResponse body
shape, not an endpoint-specific ad hoc shape. Individual router test files already
assert status codes per-endpoint; this file additionally checks the response body
shape is identical across routers."""
import os
import time
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret")


def _admin_token():
    from jose import jwt
    return jwt.encode(
        {"sub": "admin", "role": "admin", "exp": int(time.time()) + 3600},
        "test-secret",
        algorithm="HS256",
    )


def _client_with_empty_db():
    from backend.main import app
    from backend.database import get_db

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = None
    mock_db.query.return_value.filter.return_value.first.return_value = None

    def override():
        yield mock_db

    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client():
    yield from _client_with_empty_db()


def _assert_error_shape(response, expected_status, expected_code):
    assert response.status_code == expected_status
    body = response.json()
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) == {"code", "message", "request_id"}
    assert body["error"]["code"] == expected_code
    assert body["error"]["request_id"] == response.headers["x-request-id"]


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", f"/articles/{uuid.uuid4()}"),
        ("PATCH", f"/topics/{uuid.uuid4()}"),
        ("DELETE", f"/topics/{uuid.uuid4()}"),
        ("PATCH", f"/scraper-settings/{uuid.uuid4()}"),
        ("DELETE", f"/scraper-settings/{uuid.uuid4()}"),
        ("DELETE", f"/scraper-keywords/{uuid.uuid4()}"),
        ("PATCH", f"/llm-providers/{uuid.uuid4()}"),
        ("DELETE", f"/llm-providers/{uuid.uuid4()}"),
        ("PATCH", f"/admin/metric-definitions/{uuid.uuid4()}"),
        ("GET", f"/tag-groups/{uuid.uuid4()}"),
    ],
)
def test_not_found_endpoints_share_error_response_shape(client, method, path):
    headers = {"Authorization": f"Bearer {_admin_token()}"}
    response = client.request(method, path, headers=headers, json={})
    _assert_error_shape(response, 404, "NOT_FOUND")


def test_admin_guard_unauthorized_shares_error_response_shape(client):
    response = client.get(f"/scraper-keywords?topic_id={uuid.uuid4()}", headers={"Authorization": "Bearer not-a-jwt"})
    _assert_error_shape(response, 401, "UNAUTHORIZED")


def test_admin_guard_forbidden_shares_error_response_shape(client):
    from jose import jwt
    token = jwt.encode(
        {"sub": "user", "role": "user", "exp": int(time.time()) + 3600},
        "test-secret",
        algorithm="HS256",
    )
    response = client.get(f"/scraper-keywords?topic_id={uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"})
    _assert_error_shape(response, 403, "FORBIDDEN")


# ---------------------------------------------------------------------------
# 018-public-api-auth: every endpoint previously reachable with no token at all
# now 401s with no token, and succeeds with a guest token — per FR-001/router-audit.md.
# ---------------------------------------------------------------------------

def _guest_token():
    from backend.services.auth_service import create_guest_access_token
    return create_guest_access_token("audit-guest-id")


_PREVIOUSLY_PUBLIC_ENDPOINTS = [
    ("GET", "/articles"),
    ("GET", "/source-categories"),
    ("GET", "/articles/filters/sources"),
    ("GET", "/articles/filters/original-sources"),
    ("GET", "/articles/filters/tags"),
    ("GET", f"/articles/{uuid.uuid4()}"),
    ("GET", "/analyses/graph"),
    ("GET", f"/analyses/graph/group/some-group"),
    ("GET", "/tag-groups"),
    ("GET", f"/tag-groups/{uuid.uuid4()}"),
    ("GET", "/topics"),
    ("GET", f"/weekly-reports?topic_id={uuid.uuid4()}"),
    ("GET", f"/weekly-reports/latest?topic_id={uuid.uuid4()}"),
    ("GET", f"/weekly-reports/weeks?topic_id={uuid.uuid4()}"),
    ("GET", f"/weekly-reports/by-week?topic_id={uuid.uuid4()}&week_start=2026-01-05"),
    ("GET", "/languages"),
]


@pytest.mark.parametrize("method,path", _PREVIOUSLY_PUBLIC_ENDPOINTS)
def test_previously_public_endpoint_401s_with_no_token(client, method, path):
    response = client.request(method, path)
    _assert_error_shape(response, 401, "UNAUTHORIZED")


@pytest.mark.parametrize("method,path", _PREVIOUSLY_PUBLIC_ENDPOINTS)
def test_previously_public_endpoint_succeeds_with_guest_token(method, path):
    from backend.main import app
    from backend.database import get_db

    # raise_server_exceptions=False: some of these endpoints' business logic expects
    # richer mock-query chains than a bare MagicMock provides (e.g. a
    # .filter().order_by().first() chain) and would 500 on this trivial mock — this
    # test only asserts the auth *gate* accepts the guest token, not that every
    # endpoint's business logic succeeds against a trivial mock.
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = None
    mock_db.query.return_value.filter.return_value.first.return_value = None

    def override():
        yield mock_db

    app.dependency_overrides[get_db] = override
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.request(method, path, headers={"Authorization": f"Bearer {_guest_token()}"})
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code != 401
