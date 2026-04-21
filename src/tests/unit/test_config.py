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


def test_load_providers_returns_list():
    from src.config.providers import load_providers
    providers = load_providers()
    assert isinstance(providers, list)
    assert len(providers) >= 1


def test_load_providers_sorted_by_priority():
    from src.config.providers import load_providers
    providers = load_providers()
    priorities = [p['priority'] for p in providers]
    assert priorities == sorted(priorities)


def test_load_providers_required_keys():
    from src.config.providers import load_providers
    for p in load_providers():
        assert 'name' in p
        assert 'priority' in p
        assert 'model' in p
        assert 'api_key_env' in p
        assert 'strategy' in p
        assert 'type' in p['strategy']


def test_load_providers_custom_path(tmp_path):
    from src.config.providers import load_providers
    toml_content = """
[[providers]]
name = "test"
priority = 1
model = "test-model"
api_key_env = "TEST_API_KEY"

[providers.strategy]
type = "noop"
"""
    p = tmp_path / "providers.toml"
    p.write_text(toml_content)
    providers = load_providers(path=str(p))
    assert len(providers) == 1
    assert providers[0]['name'] == 'test'


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