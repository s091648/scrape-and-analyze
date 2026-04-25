import os

from src.shared.logging import get_logger
from src.modules.collection.application.events import PipelineCompletedEvent
from .base_notifier import BaseNotifier
from .telegram import TelegramNotifier

logger = get_logger(__name__)


class NotificationHandler:
    def __init__(self, notifiers: list[BaseNotifier]) -> None:
        self._notifiers = notifiers

    def handle(self, event: PipelineCompletedEvent) -> None:
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