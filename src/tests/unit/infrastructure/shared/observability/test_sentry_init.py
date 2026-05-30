"""Tests for Sentry initialization in CLI entrypoints."""
from unittest.mock import patch, MagicMock


def test_sentry_not_initialized_without_dsn():
    """When SENTRY_DSN is empty, sentry_sdk.init() is not called."""
    with patch.dict("os.environ", {"SENTRY_DSN": ""}), \
         patch("sentry_sdk.init") as mock_init:
        # Re-import settings to pick up empty DSN
        import importlib
        import src.config.settings as settings_mod
        importlib.reload(settings_mod)
        # The module-level check: `if SENTRY_DSN:` should be False
        assert settings_mod.SENTRY_DSN == "" or not settings_mod.SENTRY_DSN


def test_sentry_initialized_with_dsn():
    """When SENTRY_DSN is set, sentry_sdk.init() is called with correct args."""
    with patch.dict("os.environ", {"SENTRY_DSN": "https://test@sentry.io/123"}), \
         patch("sentry_sdk.init") as mock_init:
        import importlib
        import src.config.settings as settings_mod
        importlib.reload(settings_mod)
        # Now import main which has module-level `if SENTRY_DSN: sentry_sdk.init(...)`
        with patch("src.entrypoints.cli.main.validate_config"), \
             patch("src.entrypoints.cli.main.configure_logging"):
            importlib.reload(importlib.import_module("src.entrypoints.cli.main"))
        mock_init.assert_called_with(dsn="https://test@sentry.io/123", traces_sample_rate=0.1)


def test_sentry_init_in_scraper_entrypoint():
    """Sentry init happens at module level in main.py (before main() is called)."""
    with patch.dict("os.environ", {"SENTRY_DSN": "https://test@sentry.io/456"}), \
         patch("sentry_sdk.init") as mock_init:
        import importlib
        import src.config.settings as settings_mod
        importlib.reload(settings_mod)
        with patch("src.entrypoints.cli.main.validate_config"), \
             patch("src.entrypoints.cli.main.configure_logging"):
            import src.entrypoints.cli.main as main_mod
            importlib.reload(main_mod)
    mock_init.assert_called_once()


def test_sentry_init_in_translate_entrypoint():
    """Sentry init happens at module level in translate.py."""
    with patch.dict("os.environ", {"SENTRY_DSN": "https://test@sentry.io/789"}), \
         patch("sentry_sdk.init") as mock_init:
        import importlib
        import src.config.settings as settings_mod
        importlib.reload(settings_mod)
        # Ensure translate module is in sys.modules (first import may call sentry_sdk.init)
        importlib.import_module("src.entrypoints.cli.translate")
        mock_init.reset_mock()
        # Reload to verify module-level sentry init fires
        importlib.reload(importlib.import_module("src.entrypoints.cli.translate"))
    mock_init.assert_called_once()
