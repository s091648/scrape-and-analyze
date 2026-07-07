"""Tests for build_notification_handler() with and without Telegram env vars."""
import pytest


@pytest.fixture
def no_telegram(monkeypatch):
    monkeypatch.setattr("src.config.settings.TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr("src.config.settings.TELEGRAM_CHAT_ID", "")


@pytest.fixture
def with_telegram(monkeypatch):
    monkeypatch.setattr("src.config.settings.TELEGRAM_BOT_TOKEN", "bot123")
    monkeypatch.setattr("src.config.settings.TELEGRAM_CHAT_ID", "chat456")


def test_build_notification_handler_without_env(no_telegram):
    """Returns handler with empty senders list when env vars are missing."""
    from src.infrastructure.shared.notifications.notification_service import build_notification_handler
    handler = build_notification_handler()
    assert len(handler._senders) == 0


def test_build_notification_handler_with_telegram_env(with_telegram):
    """Registers one sender when both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set."""
    from src.infrastructure.shared.notifications.notification_service import build_notification_handler
    handler = build_notification_handler()
    assert len(handler._senders) == 1


def test_build_notification_handler_missing_token(monkeypatch):
    """Returns handler with empty senders when only TELEGRAM_CHAT_ID is set."""
    monkeypatch.setattr("src.config.settings.TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr("src.config.settings.TELEGRAM_CHAT_ID", "chat456")
    from src.infrastructure.shared.notifications.notification_service import build_notification_handler
    handler = build_notification_handler()
    assert len(handler._senders) == 0


def test_build_notification_handler_missing_chat_id(monkeypatch):
    """Returns handler with empty senders when only TELEGRAM_BOT_TOKEN is set."""
    monkeypatch.setattr("src.config.settings.TELEGRAM_BOT_TOKEN", "bot123")
    monkeypatch.setattr("src.config.settings.TELEGRAM_CHAT_ID", "")
    from src.infrastructure.shared.notifications.notification_service import build_notification_handler
    handler = build_notification_handler()
    assert len(handler._senders) == 0


def test_registered_sender_dispatches_event(with_telegram):
    """When invoked, the registered sender builds a TelegramMessage and calls the client."""
    from unittest.mock import MagicMock, patch
    from src.infrastructure.shared.notifications.notification_service import build_notification_handler
    from src.modules.collection.application.events import PipelineCompletedEvent
    from src.modules.collection.application.use_cases import SourceStats

    handler = build_notification_handler()
    sender = handler._senders[0]

    with patch(
        "src.shared.infrastructure.notifications.telegram_notifier_client.requests.post"
    ) as mock_post:
        mock_post.return_value = MagicMock(ok=True, status_code=200, text="ok")
        handler.handle(
            PipelineCompletedEvent(
                stats=[SourceStats(source="arxiv", new=1, duplicate=0, failed=0)],
                duration_seconds=1.0,
            )
        )

    assert mock_post.called
    assert mock_post.call_args.kwargs["json"]["chat_id"] == "chat456"
    assert "arxiv" in mock_post.call_args.kwargs["json"]["text"]
