import re
from datetime import datetime, timezone

from src.modules.collection.application.events import MetricsRefreshCompletedEvent
from src.shared.domain.value_objects.telegram_message import TelegramMessage


def _esc(s: str) -> str:
    """Escape MarkdownV2 special characters in a string."""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', s)


class MetricsRefreshMessageBuilder:
    """Builds a MarkdownV2 TelegramMessage describing a metrics-refresh job completion event."""

    @staticmethod
    def build(event: MetricsRefreshCompletedEvent) -> TelegramMessage:
        """Format and return a TelegramMessage for the given metrics-refresh completion event."""
        return TelegramMessage(
            text=_render(event),
            parse_mode="MarkdownV2",
        )


def _render(event: MetricsRefreshCompletedEvent) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    footer = (
        f"⚠ 有 {event.failed} 篇更新失敗，請檢查 log"
        if event.failed > 0
        else "✅ 全部完成"
    )

    plain = _esc(
        f"📊 Metrics Refresh 任務完成\n\n"
        f"📅 {now}\n"
        f"⏱ 耗時：{event.duration_seconds:.1f} 秒\n"
        f"📦 目標文章數：{event.total}\n"
        f"✅ 更新成功：{event.refreshed}\n"
        f"❌ 更新失敗：{event.failed}"
    )

    return f"{plain}\n\n{_esc(footer)}"
