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


# ---------------------------------------------------------------------------
# _int_or_none helper
# ---------------------------------------------------------------------------

def test_int_or_none_returns_int_for_valid_value(monkeypatch):
    monkeypatch.setenv("RAG_DENSE_RPM", "100")
    import importlib
    import src.config.settings as m
    importlib.reload(m)
    assert m.RAG_DENSE_RPM == 100


def test_int_or_none_returns_none_for_empty_value(monkeypatch):
    monkeypatch.setenv("RAG_DENSE_RPM", "")
    import importlib
    import src.config.settings as m
    importlib.reload(m)
    assert m.RAG_DENSE_RPM is None


def test_int_or_none_returns_none_for_invalid_string(monkeypatch):
    monkeypatch.setenv("RAG_DENSE_RPM", "not_a_number")
    import importlib
    import src.config.settings as m
    importlib.reload(m)
    assert m.RAG_DENSE_RPM is None


# ---------------------------------------------------------------------------
# missing_rag_config
# ---------------------------------------------------------------------------

def test_missing_rag_config_returns_empty_when_all_set(monkeypatch):
    monkeypatch.setenv("VECTOR_DB_NAME", "mydb")
    monkeypatch.setenv("VECTOR_DB_USER", "dbuser")
    monkeypatch.setenv("VECTOR_DB_PASSWORD", "secret")
    import importlib
    import src.config.settings as m
    importlib.reload(m)
    assert m.missing_rag_config() == []


def test_missing_rag_config_returns_all_three_when_none_set(monkeypatch):
    monkeypatch.delenv("VECTOR_DB_NAME", raising=False)
    monkeypatch.delenv("VECTOR_DB_USER", raising=False)
    monkeypatch.delenv("VECTOR_DB_PASSWORD", raising=False)
    import importlib
    import src.config.settings as m
    importlib.reload(m)
    missing = m.missing_rag_config()
    assert "VECTOR_DB_NAME" in missing
    assert "VECTOR_DB_USER" in missing
    assert "VECTOR_DB_PASSWORD" in missing


def test_missing_rag_config_returns_only_missing_vars(monkeypatch):
    monkeypatch.setenv("VECTOR_DB_NAME", "mydb")
    monkeypatch.delenv("VECTOR_DB_USER", raising=False)
    monkeypatch.delenv("VECTOR_DB_PASSWORD", raising=False)
    import importlib
    import src.config.settings as m
    importlib.reload(m)
    missing = m.missing_rag_config()
    assert "VECTOR_DB_NAME" not in missing
    assert "VECTOR_DB_USER" in missing
    assert "VECTOR_DB_PASSWORD" in missing


# ---------------------------------------------------------------------------
# log_config_warnings
# ---------------------------------------------------------------------------

def test_log_config_warnings_warns_on_missing_sentry_dsn(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "")
    monkeypatch.setenv("VECTOR_DB_NAME", "db")
    monkeypatch.setenv("VECTOR_DB_USER", "user")
    monkeypatch.setenv("VECTOR_DB_PASSWORD", "pass")
    import importlib
    import src.config.settings as m
    importlib.reload(m)
    from unittest.mock import MagicMock
    mock_logger = MagicMock()
    m.log_config_warnings(mock_logger)
    mock_logger.warning.assert_any_call("sentry_dsn_not_set")


def test_log_config_warnings_warns_on_missing_rag_config(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://sentry.io/dsn")
    monkeypatch.delenv("VECTOR_DB_NAME", raising=False)
    monkeypatch.delenv("VECTOR_DB_USER", raising=False)
    monkeypatch.delenv("VECTOR_DB_PASSWORD", raising=False)
    import importlib
    import src.config.settings as m
    importlib.reload(m)
    from unittest.mock import MagicMock
    mock_logger = MagicMock()
    m.log_config_warnings(mock_logger)
    mock_logger.warning.assert_any_call("rag_config_incomplete_rag_disabled", missing_vars=m.missing_rag_config())


# ---------------------------------------------------------------------------
# TRANSLATION_LANGUAGES
# ---------------------------------------------------------------------------

def test_translation_languages_parses_comma_separated(monkeypatch):
    monkeypatch.setenv("TRANSLATION_LANGUAGES", "zh-TW,en,ja")
    import importlib
    import src.config.settings as m
    importlib.reload(m)
    assert m.TRANSLATION_LANGUAGES == ["zh-TW", "en", "ja"]


def test_translation_languages_strips_whitespace(monkeypatch):
    monkeypatch.setenv("TRANSLATION_LANGUAGES", " zh-TW , en ")
    import importlib
    import src.config.settings as m
    importlib.reload(m)
    assert m.TRANSLATION_LANGUAGES == ["zh-TW", "en"]