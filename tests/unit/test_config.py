import pytest
import os
from unittest.mock import patch


def test_config_loads_database_url():
    """Config should load DATABASE_URL from environment"""
    with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://test:test@localhost/db'}):
        import importlib
        import src.config as config_module
        importlib.reload(config_module)

        assert config_module.DATABASE_URL == 'postgresql://test:test@localhost/db'



def test_get_sources_returns_only_active_daily():
    """get_sources('daily', session) should return active daily sources from DB"""
    from src.config import get_sources
    from unittest.mock import MagicMock

    mock_rss = MagicMock()
    mock_rss.name = 'techcrunch'
    mock_rss.url = 'https://techcrunch.com/feed/'
    mock_rss.source_type = 'rss'
    mock_rss.selector_config = None

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_rss]

    sources = get_sources('daily', session=mock_session)

    assert len(sources) == 1
    assert sources[0]['source'] == 'techcrunch'
    assert sources[0]['url'] == 'https://techcrunch.com/feed/'


def test_get_sources_emits_critical_log_when_empty():
    """get_sources should log critical when no active sources found"""
    from src.config import get_sources
    from unittest.mock import MagicMock

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = []

    with patch('src.config.logger') as mock_logger:
        sources = get_sources('daily', session=mock_session)

    assert sources == []
    mock_logger.critical.assert_called_once()


def test_rss_sources_and_blog_sources_constants_do_not_exist():
    """RSS_SOURCES and BLOG_SOURCES hardcoded constants should be removed"""
    import importlib
    import src.config as cfg
    importlib.reload(cfg)

    assert not hasattr(cfg, 'RSS_SOURCES'), "RSS_SOURCES should not exist"
    assert not hasattr(cfg, 'BLOG_SOURCES'), "BLOG_SOURCES should not exist"


def test_validate_config_raises_on_missing_database_url():
    """validate_config should raise if DATABASE_URL is missing"""
    from src.config import validate_config

    with patch.dict(os.environ, {'DATABASE_URL': ''}):
        with pytest.raises(ValueError, match="DATABASE_URL"):
            validate_config()


def test_validate_config_passes_with_database_url():
    """validate_config should pass when DATABASE_URL is set"""
    from src.config import validate_config

    with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://test:test@localhost/db'}):
        validate_config()


def test_load_providers_returns_list():
    from src.config import load_providers
    providers = load_providers()
    assert isinstance(providers, list)
    assert len(providers) >= 1


def test_load_providers_sorted_by_priority():
    from src.config import load_providers
    providers = load_providers()
    priorities = [p['priority'] for p in providers]
    assert priorities == sorted(priorities)


def test_load_providers_required_keys():
    from src.config import load_providers
    for p in load_providers():
        assert 'name' in p
        assert 'priority' in p
        assert 'model' in p
        assert 'api_key_env' in p
        assert 'strategy' in p
        assert 'type' in p['strategy']


def test_load_providers_custom_path(tmp_path):
    import tomllib
    from src.config import load_providers

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
    assert providers[0]['strategy']['type'] == 'noop'


def test_scraper_setting_frequency_is_integer():
    """ScraperSetting.frequency should be Integer type"""
    from sqlalchemy import Integer
    from backend.models.scraper_setting import ScraperSetting
    col_type = ScraperSetting.__table__.c.frequency.type
    assert isinstance(col_type, Integer)

def test_scraper_setting_has_last_scraped_at():
    """ScraperSetting should have last_scraped_at column"""
    from backend.models.scraper_setting import ScraperSetting
    assert hasattr(ScraperSetting, 'last_scraped_at')
    col = ScraperSetting.__table__.c.last_scraped_at
    assert col.nullable is True
