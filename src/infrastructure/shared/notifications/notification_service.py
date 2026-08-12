"""Job completion notification dispatch.

NotificationHandler fans a completion event (PipelineCompletedEvent and, since
020-redis-caching-layer, MetricsRefreshCompletedEvent / RagBackfillCompletedEvent) out to
a list of sender callables. Each sender is a thin closure built by
build_notification_handler() that wires a content builder + transport (Telegram client)
for a target chat.

This module owns no Telegram-specific formatting — that's the job of the per-event
message builder (e.g. PipelineCompletedMessageBuilder) passed into build_notification_handler().
"""
from typing import Any, Callable

from src.shared.logging import get_logger

logger = get_logger(__name__)


class NotificationHandler:
    """Dispatches job completion events to all registered sender callables.

    Event-agnostic — usable for any completion event shape, as long as the message
    builder passed to build_notification_handler() knows how to render it."""
    def __init__(self, senders: list[Callable[[Any], None]]) -> None:
        self._senders = senders

    def handle(self, event: Any) -> None:
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


def build_notification_handler(message_builder=None) -> NotificationHandler:
    """Build a NotificationHandler with a Telegram sender if env vars are configured.

    `message_builder` must expose `build(event) -> TelegramMessage`; defaults to
    PipelineCompletedMessageBuilder for backward compatibility with the main scrape
    pipeline's existing call site. Returns a handler with an empty senders list (and a
    warning log) when TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is unset.
    """
    from src.config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    from src.infrastructure.shared.notifications.telegram_notifier_client import TelegramNotifierClient
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    if message_builder is None:
        message_builder = PipelineCompletedMessageBuilder

    senders: list[Callable[[Any], None]] = []
    token = TELEGRAM_BOT_TOKEN
    chat_id = TELEGRAM_CHAT_ID
    if token and chat_id:
        notifier = TelegramNotifierClient(bot_token=token)

        def sender(event: Any) -> None:
            message = message_builder.build(event)
            notifier.send(chat_id, message)

        senders.append(sender)
    else:
        missing = [
            k for k, v in {"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": chat_id}.items()
            if not v
        ]
        logger.warning("telegram_notifier_disabled", missing_env_vars=missing)
    return NotificationHandler(senders)
