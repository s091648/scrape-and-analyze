"""Unit tests for scripts/export_openapi_schema.py (026-rate-limit-codegen US5)."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/testdb")

from scripts.export_openapi_schema import (  # noqa: E402
    build_openapi_schema,
    find_coverage_gaps,
)


def test_regenerating_from_an_unchanged_app_is_idempotent():
    """FR-010: two consecutive exports of the same app produce byte-identical output."""
    first = json.dumps(build_openapi_schema(), sort_keys=True)
    second = json.dumps(build_openapi_schema(), sort_keys=True)
    assert first == second


def test_coverage_gap_report_flags_auth_register_untyped_request_body():
    """FR-013: /auth/register takes a raw `dict` body (backend/routers/auth.py), so it
    has no Pydantic-defined request schema and must show up as a gap."""
    schema = build_openapi_schema()
    gaps = find_coverage_gaps(schema)
    register_gap = next(
        (g for g in gaps if g["path"] == "/auth/register" and g["method"] == "POST"), None,
    )
    assert register_gap is not None
    assert "request body has no defined schema" in register_gap["reasons"]


def test_coverage_gap_report_does_not_flag_a_fully_typed_endpoint():
    """GET /topics has both a defined response_model and no request body — must not
    appear in the gap report at all."""
    schema = build_openapi_schema()
    gaps = find_coverage_gaps(schema)
    assert not any(g["path"] == "/topics" and g["method"] == "GET" for g in gaps)
