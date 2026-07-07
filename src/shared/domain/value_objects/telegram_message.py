from dataclasses import dataclass


@dataclass(frozen=True)
class TelegramMessage:
    """Transport-agnostic representation of a Telegram message to be sent."""

    text: str
    parse_mode: str = "Markdown"
