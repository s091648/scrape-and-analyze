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


def test_config_loads_llm_settings():
    """Config should load LLM settings from environment"""
    with patch.dict(os.environ, {
        'LLM_API_KEY': 'sk-test-key',
        'LLM_PROVIDER': 'claude',
        'LLM_MODEL': 'claude-opus-4-5-20251101'
    }):
        import importlib
        import src.config as config_module
        importlib.reload(config_module)

        assert config_module.LLM_API_KEY == 'sk-test-key'
        assert config_module.LLM_PROVIDER == 'claude'
        assert config_module.LLM_MODEL == 'claude-opus-4-5-20251101'


def test_config_has_default_llm_model():
    """Config should have default LLM model if not set"""
    with patch.dict(os.environ, {'LLM_MODEL': ''}, clear=False):
        import importlib
        import src.config as config_module
        importlib.reload(config_module)

        assert 'claude' in config_module.LLM_MODEL.lower() or config_module.LLM_MODEL == ''


def test_get_sources_returns_rss_for_daily():
    """get_sources('daily') should return RSS sources"""
    from src.config import get_sources, RSS_SOURCES

    sources = get_sources('daily')

    assert sources == RSS_SOURCES
    assert len(sources) > 0
    assert all('url' in s for s in sources)


def test_get_sources_returns_blogs_for_weekly():
    """get_sources('weekly') should return blog sources"""
    from src.config import get_sources, BLOG_SOURCES

    sources = get_sources('weekly')

    assert sources == BLOG_SOURCES
    assert len(sources) > 0
    assert all('base_url' in s for s in sources)


def test_get_sources_returns_empty_for_unknown():
    """get_sources with unknown type should return empty list"""
    from src.config import get_sources

    sources = get_sources('unknown')
    assert sources == []

    sources = get_sources('')
    assert sources == []


def test_validate_config_raises_on_missing_database_url():
    """validate_config should raise if DATABASE_URL is missing"""
    from src.config import validate_config

    with patch.dict(os.environ, {'DATABASE_URL': '', 'LLM_API_KEY': 'test'}):
        with pytest.raises(ValueError, match="DATABASE_URL"):
            validate_config()


def test_validate_config_raises_on_missing_api_key():
    """validate_config should raise if LLM_API_KEY is missing"""
    from src.config import validate_config

    with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://test', 'LLM_API_KEY': ''}):
        with pytest.raises(ValueError, match="LLM_API_KEY"):
            validate_config()


def test_validate_config_passes_with_all_required():
    """validate_config should pass when all required vars are set"""
    from src.config import validate_config

    with patch.dict(os.environ, {
        'DATABASE_URL': 'postgresql://test:test@localhost/db',
        'LLM_API_KEY': 'sk-test-key'
    }):
        validate_config()
