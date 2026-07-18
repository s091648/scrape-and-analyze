import requests

from src.shared.domain.services.telegram_notifier_service import TelegramNotifierService
from src.shared.domain.value_objects.telegram_message import TelegramMessage
from src.shared.logging import get_logger

logger = get_logger(__name__)

# Telegram caption length limit for sendPhoto (vs. 4096 for sendMessage text).
_CAPTION_MAX_LENGTH = 1024


class TelegramNotifierClient(TelegramNotifierService):
    """HTTP client for the Telegram Bot API sendMessage/sendPhoto endpoints.

    Pure transport — does no content formatting. Use a per-module
    message builder to construct the TelegramMessage before calling send().
    """

    def __init__(self, bot_token: str, timeout: int = 10) -> None:
        if not bot_token:
            raise ValueError("Telegram bot_token is required")
        self._bot_token = bot_token
        self._timeout = timeout

    def send(self, chat_id: str, message: TelegramMessage) -> None:
        """POST a message to Telegram; raises requests.HTTPError on failure.

        Uses sendPhoto (with the text as caption) when photo_url is set,
        since Telegram has no way to attach an image to a plain text message.
        """
        if message.photo_url:
            self._send_photo(chat_id, message)
        else:
            self._send_message(chat_id, message)

    def _send_message(self, chat_id: str, message: TelegramMessage) -> None:
        response = requests.post(
            f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message.text, "parse_mode": message.parse_mode},
            timeout=self._timeout,
        )
        self._raise_for_status(response, chat_id)

    def _send_photo(self, chat_id: str, message: TelegramMessage) -> None:
        caption = message.text
        if len(caption) > _CAPTION_MAX_LENGTH:
            caption = caption[: _CAPTION_MAX_LENGTH - 1] + "…"
        response = requests.post(
            f"https://api.telegram.org/bot{self._bot_token}/sendPhoto",
            json={
                "chat_id": chat_id,
                "photo": message.photo_url,
                "caption": caption,
                "parse_mode": message.parse_mode,
            },
            timeout=self._timeout,
        )
        self._raise_for_status(response, chat_id)

    def _raise_for_status(self, response: requests.Response, chat_id: str) -> None:
        if not response.ok:
            logger.error(
                "telegram_send_failed",
                chat_id=chat_id,
                status_code=response.status_code,
                response_body=response.text[:500],
            )
        response.raise_for_status()
