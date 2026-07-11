from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TelegramMessage:
    """Transport-agnostic representation of a Telegram message to be sent."""

    text: str
    parse_mode: str = "Markdown"
    photo_url: Optional[str] = None
