from unittest.mock import MagicMock
from uuid import uuid4


def _make_setting_row(source_type="rss"):
    s = MagicMock()
    s.id = uuid4()
    s.name = "test-source"
    s.url = "https://example.com/feed"
    s.source_type = source_type
    s.selector_config = {}
    s.frequency = 24
    s.topic_id = uuid4()
    s.prompt_override = "Custom prompt."
    s.is_active = True
    s.last_scraped_at = None
    return s


def test_get_active_due_returns_scraper_setting_entities():
    from src.infrastructure.persistence.collection.scraper_setting_repo_impl import (
        SqlAlchemyScraperSettingRepository,
    )
    from src.modules.collection.domain.entities import ScraperSetting

    row = _make_setting_row()
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = [row]

    repo = SqlAlchemyScraperSettingRepository(session=session)
    results = repo.get_active_due()

    assert len(results) == 1
    assert isinstance(results[0], ScraperSetting)


def test_get_active_due_includes_topic_id():
    from src.infrastructure.persistence.collection.scraper_setting_repo_impl import (
        SqlAlchemyScraperSettingRepository,
    )

    row = _make_setting_row()
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = [row]

    repo = SqlAlchemyScraperSettingRepository(session=session)
    results = repo.get_active_due()

    assert results[0].topic_id == row.topic_id


def test_get_active_due_includes_prompt_override():
    from src.infrastructure.persistence.collection.scraper_setting_repo_impl import (
        SqlAlchemyScraperSettingRepository,
    )

    row = _make_setting_row()
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = [row]

    repo = SqlAlchemyScraperSettingRepository(session=session)
    results = repo.get_active_due()

    assert results[0].prompt_override == "Custom prompt."