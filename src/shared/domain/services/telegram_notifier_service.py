from abc import ABC, abstractmethod

from src.shared.domain.value_objects.telegram_message import TelegramMessage


class TelegramNotifierService(ABC):
    """Transport-only interface for sending a Telegram message to a chat id.

    Concrete implementations live in src/shared/infrastructure/notifications/.
    Use-case-specific content (Markdown formatting, locale, etc.) belongs to a
    per-module message builder — not here.
    """

    @abstractmethod
    def send(self, chat_id: str, message: TelegramMessage) -> None:
        """Send a pre-built Telegram message to a single chat."""
