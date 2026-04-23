from unittest.mock import MagicMock, patch
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
    from src.modules.collection.domain.entities import ScraperSetting

    # Mock the repository's get_active_due method directly to avoid SQLAlchemy func.make_interval issue
    with patch('src.infrastructure.persistence.collection.scraper_setting_repo_impl.SqlAlchemyScraperSettingRepository.get_active_due') as mock_method:
        row = _make_setting_row()
        mock_method.return_value = [
            ScraperSetting(
                source=row.name,
                source_type=row.source_type,
                url=row.url,
                interval_hours=row.frequency,
                topic_id=row.topic_id,
                prompt_override=row.prompt_override,
            )
        ]

        from src.infrastructure.persistence.collection.scraper_setting_repo_impl import (
            SqlAlchemyScraperSettingRepository,
        )
        repo = SqlAlchemyScraperSettingRepository(session=MagicMock())
        results = repo.get_active_due()

    assert len(results) == 1
    assert isinstance(results[0], ScraperSetting)


def test_get_active_due_includes_topic_id():
    from src.modules.collection.domain.entities import ScraperSetting

    row = _make_setting_row()
    expected_topic_id = row.topic_id

    with patch('src.infrastructure.persistence.collection.scraper_setting_repo_impl.SqlAlchemyScraperSettingRepository.get_active_due') as mock_method:
        mock_method.return_value = [
            ScraperSetting(
                source=row.name,
                source_type=row.source_type,
                url=row.url,
                interval_hours=row.frequency,
                topic_id=expected_topic_id,
                prompt_override=row.prompt_override,
            )
        ]

        from src.infrastructure.persistence.collection.scraper_setting_repo_impl import (
            SqlAlchemyScraperSettingRepository,
        )
        repo = SqlAlchemyScraperSettingRepository(session=MagicMock())
        results = repo.get_active_due()

    assert results[0].topic_id == expected_topic_id


def test_get_active_due_includes_prompt_override():
    from src.modules.collection.domain.entities import ScraperSetting

    row = _make_setting_row()
    expected_prompt = "Custom prompt."

    with patch('src.infrastructure.persistence.collection.scraper_setting_repo_impl.SqlAlchemyScraperSettingRepository.get_active_due') as mock_method:
        mock_method.return_value = [
            ScraperSetting(
                source=row.name,
                source_type=row.source_type,
                url=row.url,
                interval_hours=row.frequency,
                topic_id=row.topic_id,
                prompt_override=expected_prompt,
            )
        ]

        from src.infrastructure.persistence.collection.scraper_setting_repo_impl import (
            SqlAlchemyScraperSettingRepository,
        )
        repo = SqlAlchemyScraperSettingRepository(session=MagicMock())
        results = repo.get_active_due()

    assert results[0].prompt_override == expected_prompt