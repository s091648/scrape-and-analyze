"""Tests for build_notification_handler() with and without Telegram env vars."""
from unittest.mock import patch, MagicMock


def test_build_notification_handler_without_env():
    """Returns handler with empty notifiers list when env vars are missing."""
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}, clear=False):
        from src.infrastructure.shared.notifications.notification_service import build_notification_handler
        handler = build_notification_handler()
    assert len(handler._notifiers) == 0


def test_build_notification_handler_with_telegram_env():
    """Creates a TelegramNotifier when both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set."""
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "bot123", "TELEGRAM_CHAT_ID": "chat456"}):
        from src.infrastructure.shared.notifications.notification_service import build_notification_handler
        handler = build_notification_handler()
    assert len(handler._notifiers) == 1
    from src.infrastructure.shared.notifications.telegram import TelegramNotifier
    assert isinstance(handler._notifiers[0], TelegramNotifier)


def test_build_notification_handler_missing_token():
    """Returns handler with empty notifiers when only TELEGRAM_CHAT_ID is set."""
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": "chat456"}, clear=False):
        from src.infrastructure.shared.notifications.notification_service import build_notification_handler
        handler = build_notification_handler()
    assert len(handler._notifiers) == 0


def test_build_notification_handler_missing_chat_id():
    """Returns handler with empty notifiers when only TELEGRAM_BOT_TOKEN is set."""
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "bot123", "TELEGRAM_CHAT_ID": ""}, clear=False):
        from src.infrastructure.shared.notifications.notification_service import build_notification_handler
        handler = build_notification_handler()
    assert len(handler._notifiers) == 0
