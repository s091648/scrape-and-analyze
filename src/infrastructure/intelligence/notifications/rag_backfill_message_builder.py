import re
from datetime import datetime, timezone

from src.modules.intelligence.application.events import RagBackfillCompletedEvent
from src.shared.domain.value_objects.telegram_message import TelegramMessage


def _esc(s: str) -> str:
    """Escape MarkdownV2 special characters in a string."""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', s)


class RagBackfillMessageBuilder:
    """Builds a MarkdownV2 TelegramMessage describing a RAG-backfill job completion event."""

    @staticmethod
    def build(event: RagBackfillCompletedEvent) -> TelegramMessage:
        """Format and return a TelegramMessage for the given RAG-backfill completion event."""
        return TelegramMessage(
            text=_render(event),
            parse_mode="MarkdownV2",
        )


def _render(event: RagBackfillCompletedEvent) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    footer = (
        f"⚠ 有 {event.failed} 篇補做向量化失敗，請檢查 log"
        if event.failed > 0
        else "✅ 全部完成"
    )

    plain = _esc(
        f"🧠 RAG Backfill 任務完成\n\n"
        f"📅 {now}\n"
        f"⏱ 耗時：{event.duration_seconds:.1f} 秒\n"
        f"📦 目標文章數：{event.total}\n"
        f"✅ 補做成功：{event.succeeded}\n"
        f"❌ 補做失敗：{event.failed}"
    )

    return f"{plain}\n\n{_esc(footer)}"
