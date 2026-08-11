from src.infrastructure.shared.notifications.job_completion_message_builder import JobCompletionMessageBuilder
from src.modules.collection.application.events import DedupReconcileCompletedEvent


class DedupReconcileMessageBuilder(JobCompletionMessageBuilder):
    """Builds a MarkdownV2 TelegramMessage describing a dedup_reconcile job completion event."""

    _emoji = "🔗"
    _title = "Dedup Reconcile"
    _failure_noun = "篇檢查失敗"

    @classmethod
    def _failed_count(cls, event: DedupReconcileCompletedEvent) -> int:
        return event.failed

    @classmethod
    def _render_body(cls, event: DedupReconcileCompletedEvent) -> str:
        return cls._esc(
            f"📦 檢查文章數：{event.total}\n"
            f"🩹 已修正：{event.healed}\n"
            f"🔀 已合併：{event.merged}\n"
            f"❌ 檢查失敗：{event.failed}"
        )
