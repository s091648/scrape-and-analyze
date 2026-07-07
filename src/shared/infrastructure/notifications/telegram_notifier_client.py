import requests

from src.shared.domain.services.telegram_notifier_service import TelegramNotifierService
from src.shared.domain.value_objects.telegram_message import TelegramMessage
from src.shared.logging import get_logger

logger = get_logger(__name__)


class TelegramNotifierClient(TelegramNotifierService):
    """HTTP client for the Telegram Bot API sendMessage endpoint.

    Pure transport — does no content formatting. Use a per-module
    message builder to construct the TelegramMessage before calling send().
    """

    def __init__(self, bot_token: str, timeout: int = 10) -> None:
        if not bot_token:
            raise ValueError("Telegram bot_token is required")
        self._bot_token = bot_token
        self._timeout = timeout

    def send(self, chat_id: str, message: TelegramMessage) -> None:
        """POST a message to Telegram; raises requests.HTTPError on failure."""
        response = requests.post(
            f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message.text, "parse_mode": message.parse_mode},
            timeout=self._timeout,
        )
        if not response.ok:
            logger.error(
                "telegram_send_failed",
                chat_id=chat_id,
                status_code=response.status_code,
                response_body=response.text[:500],
            )
        response.raise_for_status()
