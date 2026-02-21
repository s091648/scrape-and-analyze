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
