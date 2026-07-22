import pytest
from datetime import datetime, timedelta, timezone

from src.modules.collection.domain.entities import ScraperSetting
from src.modules.collection.domain.exceptions import InvalidScraperIntervalError


def _make_setting(**overrides):
    kwargs = dict(source="rss_test", source_type="rss", url="https://example.com/feed", interval_hours=24)
    kwargs.update(overrides)
    return ScraperSetting(**kwargs)


def test_valid_interval_hours_constructs_successfully():
    setting = _make_setting(interval_hours=6)
    assert setting.interval_hours == 6


@pytest.mark.parametrize("interval_hours", [0, -1, -24])
def test_non_positive_interval_hours_raises(interval_hours):
    with pytest.raises(InvalidScraperIntervalError):
        _make_setting(interval_hours=interval_hours)


def test_is_due_true_when_never_scraped():
    setting = _make_setting(interval_hours=24)
    assert setting.is_due() is True


def test_is_due_false_when_recently_scraped():
    setting = _make_setting(interval_hours=24, last_scraped_at=datetime.now(timezone.utc))
    assert setting.is_due() is False


def test_is_due_true_once_interval_elapsed():
    past = datetime.now(timezone.utc) - timedelta(hours=25)
    setting = _make_setting(interval_hours=24, last_scraped_at=past)
    assert setting.is_due() is True
