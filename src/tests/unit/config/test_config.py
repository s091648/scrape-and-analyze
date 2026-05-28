import pytest
import os
from unittest.mock import patch


def test_config_loads_database_url():
    with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://test:test@localhost/db'}):
        import importlib
        import src.config.settings as settings_module
        importlib.reload(settings_module)
        assert settings_module.DATABASE_URL == 'postgresql://test:test@localhost/db'


def test_validate_config_raises_on_missing_database_url():
    from src.config.settings import validate_config
    with patch.dict(os.environ, {'DATABASE_URL': ''}):
        with pytest.raises(ValueError, match="DATABASE_URL"):
            validate_config()


def test_validate_config_passes_with_database_url():
    from src.config.settings import validate_config
    with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://test:test@localhost/db'}):
        validate_config()


def test_scraper_setting_frequency_is_integer():
    from sqlalchemy import Integer
    from models.scraper_setting import ScraperSetting
    col_type = ScraperSetting.__table__.c.frequency.type
    assert isinstance(col_type, Integer)


def test_scraper_setting_has_last_scraped_at():
    from models.scraper_setting import ScraperSetting
    assert hasattr(ScraperSetting, 'last_scraped_at')
    col = ScraperSetting.__table__.c.last_scraped_at
    assert col.nullable is True