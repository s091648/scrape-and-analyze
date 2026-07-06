import requests

from src.shared.logging import get_logger

logger = get_logger(__name__)


def send_telegram_message(bot_token: str, chat_id: str, text: str, parse_mode: str = "Markdown") -> None:
    """POST a message to the Telegram Bot API sendMessage endpoint; raises on failure."""
    response = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
        timeout=10,
    )
    if not response.ok:
        logger.error(
            "telegram_send_failed",
            status_code=response.status_code,
            response_body=response.text[:500],
        )
    response.raise_for_status()
