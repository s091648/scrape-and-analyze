"""Unit tests for backend/services/scraper_settings_service.py"""
import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest


def _mock_setting(**kwargs):
    s = MagicMock()
    s.id = kwargs.get("id", uuid.uuid4())
    s.name = kwargs.get("name", "test-source")
    s.source_type = kwargs.get("source_type", "rss")
    s.url = kwargs.get("url", "https://example.com/feed")
    s.is_active = kwargs.get("is_active", True)
    s.selector_config = kwargs.get("selector_config", None)
    s.activity = None
    return s


def _make_db(all_return=None, first_return=None):
    db = MagicMock()
    q = db.query.return_value
    q.all.return_value = all_return or []
    q.filter.return_value.all.return_value = all_return or []
    q.filter.return_value.first.return_value = first_return
    q.filter_by.return_value.first.return_value = first_return
    db.execute.return_value = []  # no activity rows by default
    return db, q


# ---------------------------------------------------------------------------
# get_all_settings
# ---------------------------------------------------------------------------

def test_get_all_settings_returns_list_with_zero_activity():
    from backend.services.scraper_settings_service import get_all_settings

    setting = _mock_setting(name="feed-a")
    db, q = _make_db(all_return=[setting])

    with patch("models.scraper_setting.ScraperSetting"):
        result = get_all_settings(db)

    assert result == [setting]
    assert setting.activity == [0] * 14


def test_get_all_settings_with_topic_id_filter():
    from backend.services.scraper_settings_service import get_all_settings

    topic_id = uuid.uuid4()
    setting = _mock_setting()
    db, q = _make_db()
    q.filter.return_value.all.return_value = [setting]

    with patch("models.scraper_setting.ScraperSetting"):
        result = get_all_settings(db, topic_id=topic_id)

    assert result == [setting]
    # filter was applied for topic_id
    q.filter.assert_called_once()


def test_get_all_settings_maps_activity_rows():
    from backend.services.scraper_settings_service import get_all_settings

    today = date.today()
    cutoff = today - timedelta(days=13)

    setting = _mock_setting(name="source-x")
    db, q = _make_db(all_return=[setting])

    row = MagicMock()
    row.source = "source-x"
    row.day = today  # offset = (today - cutoff).days = 13
    row.cnt = 42
    db.execute.return_value = [row]

    with patch("models.scraper_setting.ScraperSetting"):
        get_all_settings(db)

    assert setting.activity[13] == 42
    assert setting.activity[0] == 0


def test_get_all_settings_ignores_unknown_source_in_activity():
    from backend.services.scraper_settings_service import get_all_settings

    setting = _mock_setting(name="known-source")
    db, q = _make_db(all_return=[setting])

    row = MagicMock()
    row.source = "other-source"  # not in settings
    row.day = date.today()
    row.cnt = 99
    db.execute.return_value = [row]

    with patch("models.scraper_setting.ScraperSetting"):
        get_all_settings(db)

    assert setting.activity == [0] * 14  # unchanged


# ---------------------------------------------------------------------------
# create_setting
# ---------------------------------------------------------------------------

def test_create_setting_success():
    from backend.services.scraper_settings_service import create_setting
    from backend.schemas.scraper_setting import ScraperSettingCreate

    data = ScraperSettingCreate(
        source_type="rss", name="my-feed",
        url="https://example.com/rss", frequency=60,
        topic_id=uuid.uuid4(),
    )
    mock_obj = _mock_setting()
    db, _ = _make_db()

    with patch("models.scraper_setting.ScraperSetting") as MockSS:
        MockSS.return_value = mock_obj
        result = create_setting(db, data)

    db.add.assert_called_once_with(mock_obj)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(mock_obj)
    assert result is mock_obj


# ---------------------------------------------------------------------------
# update_setting
# ---------------------------------------------------------------------------

def test_update_setting_not_found_returns_none():
    from backend.services.scraper_settings_service import update_setting
    from backend.schemas.scraper_setting import ScraperSettingUpdate

    db, _ = _make_db(first_return=None)

    with patch("models.scraper_setting.ScraperSetting"):
        result = update_setting(db, uuid.uuid4(), ScraperSettingUpdate(name="new"))

    assert result is None
    db.commit.assert_not_called()


def test_update_setting_plain_field():
    from backend.services.scraper_settings_service import update_setting
    from backend.schemas.scraper_setting import ScraperSettingUpdate

    sid = uuid.uuid4()
    existing = _mock_setting(id=sid, name="old-name")
    db, _ = _make_db(first_return=existing)

    with patch("models.scraper_setting.ScraperSetting"):
        result = update_setting(db, sid, ScraperSettingUpdate(name="new-name"))

    assert existing.name == "new-name"
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(existing)
    assert result is existing


def test_update_setting_selector_config_merges_dict():
    from backend.services.scraper_settings_service import update_setting
    from backend.schemas.scraper_setting import ScraperSettingUpdate

    sid = uuid.uuid4()
    existing = _mock_setting(id=sid)
    existing.selector_config = {"key_a": "val_a"}
    db, _ = _make_db(first_return=existing)

    with patch("models.scraper_setting.ScraperSetting"), \
         patch("backend.services.scraper_settings_service.flag_modified") as mock_fm:
        update_setting(db, sid, ScraperSettingUpdate(selector_config={"key_b": "val_b"}))

    # existing dict merged with new keys
    assert existing.selector_config["key_a"] == "val_a"
    assert existing.selector_config["key_b"] == "val_b"
    mock_fm.assert_called_once_with(existing, "selector_config")


def test_update_setting_selector_config_from_pydantic_model():
    from backend.services.scraper_settings_service import update_setting
    from backend.schemas.scraper_setting import ScraperSettingUpdate

    sid = uuid.uuid4()
    existing = _mock_setting(id=sid)
    # Simulate a Pydantic-like object stored in selector_config
    pydantic_like = MagicMock()
    pydantic_like.model_dump.return_value = {"existing_key": "existing_val"}
    existing.selector_config = pydantic_like
    db, _ = _make_db(first_return=existing)

    with patch("models.scraper_setting.ScraperSetting"), \
         patch("backend.services.scraper_settings_service.flag_modified"):
        update_setting(db, sid, ScraperSettingUpdate(selector_config={"new_key": "new_val"}))

    merged = existing.selector_config
    assert merged["existing_key"] == "existing_val"
    assert merged["new_key"] == "new_val"


# ---------------------------------------------------------------------------
# delete_setting
# ---------------------------------------------------------------------------

def test_delete_setting_success():
    from backend.services.scraper_settings_service import delete_setting

    sid = uuid.uuid4()
    mock_obj = _mock_setting(id=sid)
    db, _ = _make_db(first_return=mock_obj)

    with patch("models.scraper_setting.ScraperSetting"):
        result = delete_setting(db, sid)

    db.delete.assert_called_once_with(mock_obj)
    db.commit.assert_called_once()
    assert result is True


def test_delete_setting_not_found_returns_false():
    from backend.services.scraper_settings_service import delete_setting

    db, _ = _make_db(first_return=None)

    with patch("models.scraper_setting.ScraperSetting"):
        result = delete_setting(db, uuid.uuid4())

    assert result is False
    db.delete.assert_not_called()
