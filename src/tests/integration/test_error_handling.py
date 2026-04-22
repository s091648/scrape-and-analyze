"""
Integration tests for failure persistence and find_recent_failures.

record_failure() was removed from src/main.py in the DDD migration —
FailedTask persistence is no longer part of the standard pipeline.
The find_recent_failures / resolution tests are retained because
find_recent_failures (in src/infrastructure/persistence/database.py) is still used by monitoring.
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_failure(db_session, *, task_type="scrape", url=None,
                    resolved=False, failed_at=None):
    from models.failed_task import FailedTask

    url = url or f"https://example.com/{uuid.uuid4()}"
    failure = FailedTask(
        task_type=task_type,
        article_url=url,
        exception_type="ValueError",
        exception_message="Test error",
        resolved=resolved,
    )
    if failed_at is not None:
        failure.failed_at = failed_at
    db_session.add(failure)
    db_session.commit()
    return failure


# ---------------------------------------------------------------------------
# find_recent_failures
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_find_recent_failures_returns_unresolved_failures(db_session):
    from src.infrastructure.persistence.database import find_recent_failures

    failure = _insert_failure(db_session, resolved=False)
    recent_ids = {f.id for f in find_recent_failures(db_session, hours=24)}
    assert failure.id in recent_ids


@pytest.mark.integration
def test_find_recent_failures_excludes_resolved_failures(db_session):
    from src.infrastructure.persistence.database import find_recent_failures

    failure = _insert_failure(db_session, resolved=True)
    recent_ids = {f.id for f in find_recent_failures(db_session, hours=24)}
    assert failure.id not in recent_ids


@pytest.mark.integration
def test_find_recent_failures_excludes_old_failures(db_session):
    from src.infrastructure.persistence.database import find_recent_failures

    old_time = datetime.now(timezone.utc) - timedelta(hours=48)
    failure = _insert_failure(db_session, resolved=False, failed_at=old_time)
    recent_ids = {f.id for f in find_recent_failures(db_session, hours=24)}
    assert failure.id not in recent_ids


# ---------------------------------------------------------------------------
# Failure resolution
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_failed_task_can_be_resolved(db_session):
    from src.infrastructure.persistence.database import find_recent_failures
    from models.failed_task import FailedTask

    failure = _insert_failure(db_session, resolved=False)
    assert failure.id in {f.id for f in find_recent_failures(db_session, hours=24)}

    failure.resolved = True
    failure.resolved_at = datetime.now(timezone.utc)
    db_session.commit()

    assert failure.id not in {f.id for f in find_recent_failures(db_session, hours=24)}
