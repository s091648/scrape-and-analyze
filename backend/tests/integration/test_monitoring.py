"""
Integration tests for GET /failed-tasks.

This endpoint had zero test coverage at the HTTP/router level before this file
(only the underlying get_failed_tasks_paginated() service function was
unit-tested with mocks) — and, until this same pass added
Depends(require_admin), no auth guard at all despite returning internal
exception/traceback data. See specs/018-public-api-auth/router-audit.md.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.tests.integration.conftest import admin_token

pytestmark = pytest.mark.integration

_ADMIN_HDR = {"Authorization": f"Bearer {admin_token()}"}


def _seed_failed_task(db_session, **kwargs):
    from models.failed_task import FailedTask
    defaults = dict(
        id=uuid.uuid4(),
        task_type="analyze",
        article_url="https://example.com/article",
        exception_type="ValueError",
        exception_message="something broke",
        failed_at=datetime.now(timezone.utc),
        resolved=False,
    )
    defaults.update(kwargs)
    row = FailedTask(**defaults)
    db_session.add(row)
    db_session.flush()
    return row


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def test_list_failed_tasks_requires_auth(api_client):
    r = api_client.app_client.get("/failed-tasks")
    assert r.status_code == 401


def test_list_failed_tasks_requires_admin_role(api_client):
    # api_client attaches a guest token by default (no "role" claim) — a valid
    # token that still isn't an admin.
    r = api_client.get("/failed-tasks")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Data / pagination
# ---------------------------------------------------------------------------

def test_list_failed_tasks_returns_seeded_row(api_client, db_session):
    seeded = _seed_failed_task(db_session, exception_message="boom")

    r = api_client.get("/failed-tasks", headers=_ADMIN_HDR)
    assert r.status_code == 200
    data = r.json()
    ids = [item["id"] for item in data["items"]]
    assert str(seeded.id) in ids
    matching = next(item for item in data["items"] if item["id"] == str(seeded.id))
    assert matching["exception_message"] == "boom"


def test_list_failed_tasks_orders_newest_first(api_client, db_session):
    older = _seed_failed_task(db_session, failed_at=datetime.now(timezone.utc) - timedelta(days=1))
    newer = _seed_failed_task(db_session, failed_at=datetime.now(timezone.utc))

    r = api_client.get("/failed-tasks", headers=_ADMIN_HDR)
    assert r.status_code == 200
    ids = [item["id"] for item in r.json()["items"]]
    assert ids.index(str(newer.id)) < ids.index(str(older.id))


def test_list_failed_tasks_paginates(api_client, db_session):
    for _ in range(5):
        _seed_failed_task(db_session)

    r = api_client.get("/failed-tasks?page=1&size=2", headers=_ADMIN_HDR)
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 2
    assert data["total"] >= 5
    assert data["page"] == 1
    assert data["size"] == 2
