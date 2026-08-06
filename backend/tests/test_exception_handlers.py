from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from shared.domain.exceptions import (
    DomainError,
    ValidationError,
    NotFoundError,
    ConflictError,
    UnauthorizedError,
    ForbiddenError,
    ExternalDependencyError,
)


@pytest.fixture
def client():
    from backend.main import app

    @app.get("/__test/raise/{category}")
    def _raise(category: str):
        exceptions = {
            "validation": ValidationError("bad field value"),
            "unauthorized": UnauthorizedError("token expired"),
            "forbidden": ForbiddenError("admin role required"),
            "not_found": NotFoundError("topic not found"),
            "conflict": ConflictError("email already taken"),
            "external_dependency": ExternalDependencyError("all LLM providers exhausted"),
            "unmapped_domain": DomainError("unmapped category"),
            "non_domain": IntegrityError("stmt", "params", Exception("duplicate key value violates unique constraint")),
        }
        raise exceptions[category]

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    "category,expected_status,expected_code",
    [
        ("validation", 400, "VALIDATION_ERROR"),
        ("unauthorized", 401, "UNAUTHORIZED"),
        ("forbidden", 403, "FORBIDDEN"),
        ("not_found", 404, "NOT_FOUND"),
        ("conflict", 409, "CONFLICT"),
        ("external_dependency", 502, "EXTERNAL_DEPENDENCY_ERROR"),
        ("unmapped_domain", 500, "INTERNAL_ERROR"),
        ("non_domain", 500, "INTERNAL_ERROR"),
    ],
)
def test_category_maps_to_documented_status_and_code(client, category, expected_status, expected_code):
    with patch("backend.exceptions.handlers.capture_exception"):
        response = client.get(f"/__test/raise/{category}")
    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code


def test_response_body_matches_error_response_contract(client):
    with patch("backend.exceptions.handlers.capture_exception"):
        response = client.get("/__test/raise/not_found")
    body = response.json()
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) == {"code", "message", "request_id"}
    assert body["error"]["request_id"] == response.headers["x-request-id"]


@pytest.mark.parametrize("category", ["unmapped_domain", "non_domain"])
def test_500_message_is_generic_and_never_leaks_exception_text(client, category):
    with patch("backend.exceptions.handlers.capture_exception"):
        response = client.get(f"/__test/raise/{category}")
    message = response.json()["error"]["message"]
    assert message == "An unexpected error occurred"
    assert "unique constraint" not in message
    assert "unmapped category" not in message


def test_502_message_is_generic_and_never_leaks_exception_text(client):
    with patch("backend.exceptions.handlers.capture_exception"):
        response = client.get("/__test/raise/external_dependency")
    message = response.json()["error"]["message"]
    assert message == "An upstream dependency is unavailable"
    assert "all LLM providers exhausted" not in message


@pytest.mark.parametrize(
    "category,should_capture",
    [
        ("validation", False),
        ("unauthorized", False),
        ("forbidden", False),
        ("not_found", False),
        ("conflict", False),
        ("external_dependency", True),
        ("unmapped_domain", True),
        ("non_domain", True),
    ],
)
def test_sentry_capture_only_for_500_and_502_categories(client, category, should_capture):
    with patch("backend.exceptions.handlers.capture_exception") as mock_capture:
        client.get(f"/__test/raise/{category}")
    assert mock_capture.called is should_capture
