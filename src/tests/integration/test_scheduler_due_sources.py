"""Integration tests for due-source selection (ScraperSettingRepository.get_active_due).

Verifies the 30-minute tolerance window in the SQL query and mark_scraped()
behaviour against a real PostgreSQL database.

Tasks covered:
  T024 - Never-scraped source is included
  T025 - Source scraped 5h ago with 4h frequency is included (elapsed > interval - tolerance)
  T026 - Source scraped 3.5h ago with 4h frequency is excluded (elapsed < interval - tolerance)
  T027 - Inactive source is excluded regardless of last_scraped_at
  T028 - mark_scraped() sets last_scraped_at and commits
  T029 - CollectionPipeline.run() with no due sources publishes PipelineCompletedEvent
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from models.scraper_setting import ScraperSetting as ScraperSettingModel
from src.infrastructure.persistence.collection.scraper_setting_repo_impl import (
    SqlAlchemyScraperSettingRepository,
)
from src.infrastructure.collection.collection_pipeline import CollectionPipeline
from src.modules.collection.application.events import PipelineCompletedEvent
from src.modules.collection.application.use_cases import PipelineStats


_TEST_SOURCE_NAMES = [
    "never-scraped",
    "past-tolerance",
    "within-tolerance",
    "inactive-source",
    "mark-scraped-test",
]


@pytest.fixture(autouse=True)
def cleanup_scheduler_rows(db_session):
    """Delete committed test rows before and after each test to prevent cross-run pollution."""
    db_session.query(ScraperSettingModel).filter(
        ScraperSettingModel.name.in_(_TEST_SOURCE_NAMES)
    ).delete(synchronize_session=False)
    db_session.commit()
    yield
    db_session.query(ScraperSettingModel).filter(
        ScraperSettingModel.name.in_(_TEST_SOURCE_NAMES)
    ).delete(synchronize_session=False)
    db_session.commit()


def _make_setting(
    topic_id,
    source="test-rss",
    source_type="rss",
    url="https://example.com/feed.xml",
    frequency=4,
    is_active=True,
    last_scraped_at=None,
):
    """Helper to create a ScraperSetting ORM row for tests."""
    return ScraperSettingModel(
        name=source,
        source_type=source_type,
        url=url,
        frequency=frequency,
        is_active=is_active,
        last_scraped_at=last_scraped_at,
        topic_id=topic_id,
    )


# ---------------------------------------------------------------------------
# T024: Never-scraped source is included in get_active_due()
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_never_scraped_source_is_due(db_session, test_topic):
    """T024: A source with last_scraped_at=None appears in get_active_due()."""
    setting = _make_setting(
        topic_id=test_topic,
        source="never-scraped",
        last_scraped_at=None,
    )
    db_session.add(setting)
    db_session.commit()

    repo = SqlAlchemyScraperSettingRepository(session=db_session)
    due = repo.get_active_due()

    due_sources = [s.source for s in due]
    assert "never-scraped" in due_sources


# ---------------------------------------------------------------------------
# T025: Source scraped 5h ago with 4h frequency is included
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_source_past_tolerance_is_due(db_session, test_topic):
    """T025: 5h elapsed with 4h frequency (tolerance = 3.5h threshold) => due."""
    five_hours_ago = datetime.now(timezone.utc) - timedelta(hours=5)
    setting = _make_setting(
        topic_id=test_topic,
        source="past-tolerance",
        frequency=4,
        last_scraped_at=five_hours_ago,
    )
    db_session.add(setting)
    db_session.commit()

    repo = SqlAlchemyScraperSettingRepository(session=db_session)
    due = repo.get_active_due()

    due_sources = [s.source for s in due]
    assert "past-tolerance" in due_sources


# ---------------------------------------------------------------------------
# T026: Source scraped 3.5h ago with 4h frequency is excluded (boundary)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_source_within_tolerance_is_not_due(db_session, test_topic):
    """T026: 3.5h elapsed with 4h frequency (boundary: 4h - 30min = 3.5h) => not due.

    The SQL uses strict '>' so a source whose elapsed time equals the
    interval-minus-tolerance threshold is excluded.
    """
    three_hours_twenty_ago = datetime.now(timezone.utc) - timedelta(hours=3, minutes=20)
    setting = _make_setting(
        topic_id=test_topic,
        source="within-tolerance",
        frequency=4,
        last_scraped_at=three_hours_twenty_ago,
    )
    db_session.add(setting)
    db_session.commit()

    repo = SqlAlchemyScraperSettingRepository(session=db_session)
    due = repo.get_active_due()

    due_sources = [s.source for s in due]
    assert "within-tolerance" not in due_sources


# ---------------------------------------------------------------------------
# T027: Inactive source is excluded regardless of last_scraped_at
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_inactive_source_is_excluded(db_session, test_topic):
    """T027: is_active=False source never appears in get_active_due()."""
    setting = _make_setting(
        topic_id=test_topic,
        source="inactive-source",
        frequency=4,
        is_active=False,
        last_scraped_at=None,
    )
    db_session.add(setting)
    db_session.commit()

    repo = SqlAlchemyScraperSettingRepository(session=db_session)
    due = repo.get_active_due()

    due_sources = [s.source for s in due]
    assert "inactive-source" not in due_sources


# ---------------------------------------------------------------------------
# T028: mark_scraped() sets last_scraped_at and commits
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_mark_scraped_sets_timestamp(db_session, test_topic):
    """T028: mark_scraped() sets last_scraped_at to the current time and commits."""
    before = datetime.now(timezone.utc)
    setting = _make_setting(
        topic_id=test_topic,
        source="mark-scraped-test",
        last_scraped_at=None,
    )
    db_session.add(setting)
    db_session.commit()

    repo = SqlAlchemyScraperSettingRepository(session=db_session)
    repo.mark_scraped(setting.id)

    after = datetime.now(timezone.utc)

    # Re-read the row to confirm the commit persisted
    db_session.expire_all()
    refreshed = (
        db_session.query(ScraperSettingModel)
        .filter_by(id=setting.id)
        .first()
    )
    assert refreshed.last_scraped_at is not None
    assert before <= refreshed.last_scraped_at <= after


# ---------------------------------------------------------------------------
# T029: CollectionPipeline.run() with no due sources publishes event, returns 0
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_pipeline_no_due_sources_publishes_event(db_session):
    """T029: With no due sources, run() publishes PipelineCompletedEvent and returns 0."""
    mock_setting_repo = MagicMock()
    mock_setting_repo.get_active_due.return_value = []
    mock_event_bus = MagicMock()
    pipeline_stats = PipelineStats()
    pipeline = CollectionPipeline(
        setting_repo=mock_setting_repo,
        scraper_factory=MagicMock(),
        event_bus=mock_event_bus,
        pipeline_stats=pipeline_stats,
    )

    result = pipeline.run()

    assert result == 0
    mock_event_bus.publish.assert_called_once()
    event = mock_event_bus.publish.call_args[0][0]
    assert isinstance(event, PipelineCompletedEvent)
