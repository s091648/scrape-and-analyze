import os

from src.shared.logging import get_logger
from src.modules.collection.application.events import PipelineCompletedEvent
from .base_notifier import BaseNotifier
from .telegram import TelegramNotifier

logger = get_logger(__name__)


class NotificationHandler:
    """Dispatches pipeline completion events to all registered notifiers."""
    def __init__(self, notifiers: list[BaseNotifier]) -> None:
        self._notifiers = notifiers

    def handle(self, event: PipelineCompletedEvent) -> None:
        """Fan out the event to every notifier, swallowing individual failures."""
        for notifier in self._notifiers:
            try:
                notifier.notify(event)
            except Exception as e:
                logger.warning(
                    "notifier_failed",
                    notifier=type(notifier).__name__,
                    error=str(e),
                )


def build_notification_handler() -> NotificationHandler:
    """Build a NotificationHandler with Telegram notifier if env vars are configured."""
    notifiers: list[BaseNotifier] = []
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if token and chat_id:
        notifiers.append(TelegramNotifier(token=token, chat_id=chat_id))
    else:
        missing = [
            k for k, v in {"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": chat_id}.items()
            if not v
        ]
        logger.warning("telegram_notifier_disabled", missing_env_vars=missing)
    return NotificationHandler(notifiers)