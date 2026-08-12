from src.infrastructure.shared.notifications.job_completion_message_builder import JobCompletionMessageBuilder
from src.modules.collection.application.events import MetricsRefreshCompletedEvent


class MetricsRefreshMessageBuilder(JobCompletionMessageBuilder):
    """Builds a MarkdownV2 TelegramMessage describing a metrics-refresh job completion event."""

    _emoji = "📊"
    _title = "Metrics Refresh"
    _failure_noun = "篇更新失敗"

    @classmethod
    def _failed_count(cls, event: MetricsRefreshCompletedEvent) -> int:
        return event.failed

    @classmethod
    def _render_body(cls, event: MetricsRefreshCompletedEvent) -> str:
        lines = [
            f"📦 目標文章數：{event.total}",
            f"✅ 更新成功：{event.refreshed}",
            f"❌ 更新失敗：{event.failed}",
        ]
        if event.rate_limited_providers:
            providers = "、".join(event.rate_limited_providers)
            lines.append(f"🚫 Provider 已限流本次略過：{providers}")
        return cls._esc("\n".join(lines))
