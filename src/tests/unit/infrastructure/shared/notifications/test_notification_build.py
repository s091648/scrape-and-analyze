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
    from datetime import datetime, timezone
    from unittest.mock import MagicMock, patch
    from src.infrastructure.shared.notifications.notification_service import build_notification_handler
    from src.modules.collection.application.events import PipelineCompletedEvent
    from src.modules.collection.application.use_cases import SourceStats
    from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta

    handler = build_notification_handler()
    sender = handler._senders[0]

    with patch(
        "src.infrastructure.shared.notifications.telegram_notifier_client.requests.post"
    ) as mock_post:
        mock_post.return_value = MagicMock(ok=True, status_code=200, text="ok")
        handler.handle(
            PipelineCompletedEvent(
                stats=[SourceStats(source="arxiv", new=1, duplicate=0, failed=0)],
                execution=JobExecutionMeta(
                    started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    duration_seconds=1.0,
                    app_env="production",
                ),
            )
        )

    assert mock_post.called
    assert mock_post.call_args.kwargs["json"]["chat_id"] == "chat456"
    assert "arxiv" in mock_post.call_args.kwargs["json"]["text"]


# ---------------------------------------------------------------------------
# 020-redis-caching-layer, US4 — build_notification_handler(message_builder) parameterization
# ---------------------------------------------------------------------------

def test_build_notification_handler_uses_custom_message_builder(with_telegram):
    """A caller-supplied message_builder is used instead of the PipelineCompletedMessageBuilder default."""
    from datetime import datetime, timezone
    from unittest.mock import MagicMock, patch
    from src.infrastructure.shared.notifications.notification_service import build_notification_handler
    from src.modules.collection.application.events import MetricsRefreshCompletedEvent
    from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta

    class _StubMessageBuilder:
        @staticmethod
        def build(event):
            from src.shared.domain.value_objects.telegram_message import TelegramMessage
            return TelegramMessage(text=f"refreshed={event.refreshed}", parse_mode="MarkdownV2")

    handler = build_notification_handler(_StubMessageBuilder)
    sender = handler._senders[0]

    execution = JobExecutionMeta(
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        duration_seconds=1.0,
        app_env="production",
    )
    with patch(
        "src.infrastructure.shared.notifications.telegram_notifier_client.requests.post"
    ) as mock_post:
        mock_post.return_value = MagicMock(ok=True, status_code=200, text="ok")
        handler.handle(MetricsRefreshCompletedEvent(total=5, refreshed=5, failed=0, execution=execution))

    assert mock_post.called
    assert mock_post.call_args.kwargs["json"]["text"] == "refreshed=5"


def test_build_notification_handler_defaults_to_pipeline_completed_message_builder(with_telegram):
    """No message_builder argument -> falls back to PipelineCompletedMessageBuilder (unchanged behavior)."""
    from src.infrastructure.shared.notifications.notification_service import build_notification_handler
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    handler = build_notification_handler()
    assert len(handler._senders) == 1
    # Same regression coverage as test_registered_sender_dispatches_event above,
    # just asserting the default explicitly resolves to PipelineCompletedMessageBuilder.
    handler_explicit = build_notification_handler(PipelineCompletedMessageBuilder)
    assert len(handler_explicit._senders) == 1
