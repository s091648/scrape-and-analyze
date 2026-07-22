import pytest
from datetime import date

from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport
from src.modules.intelligence.domain.exceptions import InvalidWeeklyReportStatusError


def _make_report(**overrides):
    kwargs = dict(
        id=None,
        topic_id=None,
        week_start_date=date(2026, 1, 5),
        title="Weekly Digest",
        summary_text="summary",
        cover_image_url=None,
        article_ids=[],
        article_count=0,
        status="pending",
    )
    kwargs.update(overrides)
    return WeeklyReport(**kwargs)


@pytest.mark.parametrize("status", ["pending", "completed", "failed"])
def test_valid_status_constructs_successfully(status):
    report = _make_report(status=status)
    assert report.status == status


def test_invalid_status_raises():
    with pytest.raises(InvalidWeeklyReportStatusError):
        _make_report(status="in_progress")
