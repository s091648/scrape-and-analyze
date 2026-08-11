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
        return cls._esc(
            f"📦 目標文章數：{event.total}\n"
            f"✅ 更新成功：{event.refreshed}\n"
            f"❌ 更新失敗：{event.failed}"
        )
