"""Pipeline completion notification dispatch.

NotificationHandler fans a PipelineCompletedEvent out to a list of sender
callables. Each sender is a thin closure built by build_notification_handler()
that wires a content builder + transport (Telegram client) for a target chat.

This module owns no Telegram-specific formatting — that's the job of
PipelineCompletedMessageBuilder (per-module content).
"""
from typing import Callable

from src.shared.logging import get_logger
from src.modules.collection.application.events import PipelineCompletedEvent

logger = get_logger(__name__)


class NotificationHandler:
    """Dispatches pipeline completion events to all registered sender callables."""
    def __init__(self, senders: list[Callable[[PipelineCompletedEvent], None]]) -> None:
        self._senders = senders

    def handle(self, event: PipelineCompletedEvent) -> None:
        """Fan out the event to every sender, swallowing individual failures."""
        for sender in self._senders:
            try:
                sender(event)
            except Exception as e:
                logger.warning(
                    "notifier_failed",
                    sender=getattr(sender, "__name__", type(sender).__name__),
                    error=str(e),
                )


def build_notification_handler() -> NotificationHandler:
    """Build a NotificationHandler with a Telegram sender if env vars are configured.

    Returns a handler with an empty senders list (and a warning log) when
    TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is unset.
    """
    from src.config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    from src.infrastructure.shared.notifications.telegram_notifier_client import TelegramNotifierClient
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    senders: list[Callable[[PipelineCompletedEvent], None]] = []
    token = TELEGRAM_BOT_TOKEN
    chat_id = TELEGRAM_CHAT_ID
    if token and chat_id:
        notifier = TelegramNotifierClient(bot_token=token)

        def sender(event: PipelineCompletedEvent) -> None:
            message = PipelineCompletedMessageBuilder.build(event)
            notifier.send(chat_id, message)

        senders.append(sender)
    else:
        missing = [
            k for k, v in {"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": chat_id}.items()
            if not v
        ]
        logger.warning("telegram_notifier_disabled", missing_env_vars=missing)
    return NotificationHandler(senders)
