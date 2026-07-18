"""Unit tests for backend/services/weekly_report_service.py"""
import uuid
from datetime import date
from unittest.mock import MagicMock

import pytest


def _mock_db_query(items=None, total=0, first=None):
    """Return a mock DB session whose query chain returns specified items/total/first."""
    db = MagicMock()
    q = db.query.return_value
    q.filter.return_value = q
    q.order_by.return_value = q
    q.offset.return_value = q
    q.limit.return_value = q
    q.count.return_value = total
    q.all.return_value = items or []
    q.first.return_value = first
    return db, q


# ---------------------------------------------------------------------------
# _monday_of_week
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("d,expected_monday", [
    (date(2026, 7, 13), date(2026, 7, 13)),  # Monday itself
    (date(2026, 7, 14), date(2026, 7, 13)),  # Tuesday
    (date(2026, 7, 19), date(2026, 7, 13)),  # Sunday (end of week)
])
def test_monday_of_week(d, expected_monday):
    from backend.services.weekly_report_service import _monday_of_week
    assert _monday_of_week(d) == expected_monday


# ---------------------------------------------------------------------------
# get_weekly_report_by_week
# ---------------------------------------------------------------------------

def test_get_weekly_report_by_week_found():
    from backend.services.weekly_report_service import get_weekly_report_by_week
    report = MagicMock()
    db, q = _mock_db_query(first=report)
    topic_id = uuid.uuid4()

    result = get_weekly_report_by_week(db, topic_id, date(2026, 7, 14))

    assert result is report
    q.first.assert_called_once()


def test_get_weekly_report_by_week_not_found_returns_none():
    from backend.services.weekly_report_service import get_weekly_report_by_week
    db, q = _mock_db_query(first=None)

    result = get_weekly_report_by_week(db, uuid.uuid4(), date(2026, 7, 14))

    assert result is None


# ---------------------------------------------------------------------------
# get_weekly_report_weeks
# ---------------------------------------------------------------------------

def test_get_weekly_report_weeks_returns_flat_list():
    from backend.services.weekly_report_service import get_weekly_report_weeks
    rows = [(date(2026, 7, 13),), (date(2026, 7, 6),)]
    db, q = _mock_db_query(items=rows)

    result = get_weekly_report_weeks(db, uuid.uuid4())

    assert result == [date(2026, 7, 13), date(2026, 7, 6)]


def test_get_weekly_report_weeks_empty():
    from backend.services.weekly_report_service import get_weekly_report_weeks
    db, q = _mock_db_query(items=[])

    result = get_weekly_report_weeks(db, uuid.uuid4())

    assert result == []


# ---------------------------------------------------------------------------
# get_weekly_reports
# ---------------------------------------------------------------------------

def test_get_weekly_reports_returns_total_and_items():
    from backend.services.weekly_report_service import get_weekly_reports
    items = [MagicMock(), MagicMock()]
    db, q = _mock_db_query(items=items, total=5)

    total, result_items = get_weekly_reports(db, uuid.uuid4(), limit=2, offset=0)

    assert total == 5
    assert result_items == items


def test_get_weekly_reports_applies_offset_and_limit():
    from backend.services.weekly_report_service import get_weekly_reports
    db, q = _mock_db_query(items=[], total=0)

    get_weekly_reports(db, uuid.uuid4(), limit=10, offset=20)

    q.offset.assert_called_once_with(20)
    q.limit.assert_called_once_with(10)


# ---------------------------------------------------------------------------
# get_latest_weekly_report
# ---------------------------------------------------------------------------

def test_get_latest_weekly_report_found():
    from backend.services.weekly_report_service import get_latest_weekly_report
    report = MagicMock()
    db, q = _mock_db_query(first=report)

    result = get_latest_weekly_report(db, uuid.uuid4())

    assert result is report


def test_get_latest_weekly_report_none():
    from backend.services.weekly_report_service import get_latest_weekly_report
    db, q = _mock_db_query(first=None)

    result = get_latest_weekly_report(db, uuid.uuid4())

    assert result is None


# ---------------------------------------------------------------------------
# get_weekly_report_translations
# ---------------------------------------------------------------------------

def test_get_weekly_report_translations_short_circuits_for_english():
    from backend.services.weekly_report_service import get_weekly_report_translations
    db, q = _mock_db_query(items=[MagicMock()])

    result = get_weekly_report_translations(db, [uuid.uuid4()], "en")

    assert result == {}
    db.query.assert_not_called()


def test_get_weekly_report_translations_short_circuits_for_empty_ids():
    from backend.services.weekly_report_service import get_weekly_report_translations
    db, q = _mock_db_query(items=[MagicMock()])

    result = get_weekly_report_translations(db, [], "zh-TW")

    assert result == {}
    db.query.assert_not_called()


def test_get_weekly_report_translations_builds_dict_keyed_by_report_id():
    from backend.services.weekly_report_service import get_weekly_report_translations
    report_id_1 = uuid.uuid4()
    report_id_2 = uuid.uuid4()
    t1 = MagicMock(weekly_report_id=report_id_1)
    t2 = MagicMock(weekly_report_id=report_id_2)
    db, q = _mock_db_query(items=[t1, t2])

    result = get_weekly_report_translations(db, [report_id_1, report_id_2], "zh-TW")

    assert result == {report_id_1: t1, report_id_2: t2}
