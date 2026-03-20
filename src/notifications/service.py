import os
from src.notifications.base import BaseNotifier
from src.notifications.telegram import TelegramNotifier
from src.observability.run_summary import RunSummary
from src.utils.logging import get_logger

logger = get_logger(__name__)


def get_notifiers() -> list[BaseNotifier]:
    """
    Returns configured notifiers from env vars.

    Future extension: accept optional user_id parameter and query
    notification_settings DB table. For scraping cron (no user context),
    use a system-level admin row in that table.
    """
    notifiers: list[BaseNotifier] = []
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if token and chat_id:
        notifiers.append(TelegramNotifier(token=token, chat_id=chat_id))
    else:
        missing = [k for k, v in {"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": chat_id}.items() if not v]
        logger.error("telegram_notifier_disabled", missing_env_vars=missing)
    return notifiers


def notify_all(summary: RunSummary, duration: float) -> None:
    for notifier in get_notifiers():
        try:
            notifier.send_scrape_summary(summary, duration)
        except Exception as e:
            logger.warning(
                "notifier_failed",
                notifier=type(notifier).__name__,
                error=str(e),
            )
