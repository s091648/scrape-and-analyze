import pytest
import uuid
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_failure(db_session, *, task_type="scrape", url=None,
                    resolved=False, failed_at=None):
    """Insert and return a committed FailedTask."""
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
# record_failure
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_record_failure_creates_failed_task_in_db(db_session):
    """record_failure should persist a FailedTask with correct fields."""
    from src.main import record_failure
    from models.failed_task import FailedTask

    url = f"https://example.com/{uuid.uuid4()}"
    error = ValueError("Something went wrong")

    record_failure(db_session, "scrape", url, None, error)

    failure = db_session.query(FailedTask).filter_by(article_url=url).first()
    assert failure is not None
    assert failure.task_type == "scrape"
    assert failure.exception_type == "ValueError"
    assert failure.exception_message == "Something went wrong"
    assert failure.resolved is False


@pytest.mark.integration
def test_record_failure_with_article_id_stores_reference(db_session):
    """record_failure with an article_id should store the FK reference."""
    from src.main import record_failure
    from models.failed_task import FailedTask
    from models.article import Article
    from src.utils.sanitizer import generate_url_hash

    url = f"https://example.com/{uuid.uuid4()}"
    article = Article(
        url=url,
        url_hash=generate_url_hash(url),
        source="test",
        title="Test",
        content="Content",
        correlation_id=uuid.uuid4(),
    )
    db_session.add(article)
    db_session.commit()

    record_failure(db_session, "analyze", url, article.id, RuntimeError("LLM failed"))

    failure = db_session.query(FailedTask).filter_by(article_url=url, task_type="analyze").first()
    assert failure is not None
    assert failure.article_id == article.id
    assert failure.exception_type == "RuntimeError"


# ---------------------------------------------------------------------------
# find_recent_failures
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_find_recent_failures_returns_unresolved_failures(db_session):
    """find_recent_failures should return unresolved failures from the last 24h."""
    from src.database import find_recent_failures

    failure = _insert_failure(db_session, resolved=False)

    recent = find_recent_failures(db_session, hours=24)
    recent_ids = {f.id for f in recent}
    assert failure.id in recent_ids


@pytest.mark.integration
def test_find_recent_failures_excludes_resolved_failures(db_session):
    """find_recent_failures should not return already-resolved failures."""
    from src.database import find_recent_failures

    failure = _insert_failure(db_session, resolved=True)

    recent = find_recent_failures(db_session, hours=24)
    recent_ids = {f.id for f in recent}
    assert failure.id not in recent_ids


@pytest.mark.integration
def test_find_recent_failures_excludes_old_failures(db_session):
    """find_recent_failures should not return failures older than the time window."""
    from src.database import find_recent_failures

    old_time = datetime.now(timezone.utc) - timedelta(hours=48)
    failure = _insert_failure(db_session, resolved=False, failed_at=old_time)

    recent = find_recent_failures(db_session, hours=24)
    recent_ids = {f.id for f in recent}
    assert failure.id not in recent_ids


# ---------------------------------------------------------------------------
# Failure resolution
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_failed_task_can_be_resolved(db_session):
    """Marking a FailedTask as resolved should persist and exclude it from recent queries."""
    from src.database import find_recent_failures
    from models.failed_task import FailedTask

    failure = _insert_failure(db_session, resolved=False)
    assert failure.id in {f.id for f in find_recent_failures(db_session, hours=24)}

    # Resolve it
    failure.resolved = True
    failure.resolved_at = datetime.now(timezone.utc)
    db_session.commit()

    assert failure.id not in {f.id for f in find_recent_failures(db_session, hours=24)}
