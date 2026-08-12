from src.infrastructure.shared.notifications.job_completion_message_builder import JobCompletionMessageBuilder
from src.modules.intelligence.application.events import RagBackfillCompletedEvent


class RagBackfillMessageBuilder(JobCompletionMessageBuilder):
    """Builds a MarkdownV2 TelegramMessage describing a RAG-backfill job completion event."""

    _emoji = "🧠"
    _title = "RAG Backfill"
    _failure_noun = "篇補做向量化失敗"

    @classmethod
    def _failed_count(cls, event: RagBackfillCompletedEvent) -> int:
        return event.failed

    @classmethod
    def _render_body(cls, event: RagBackfillCompletedEvent) -> str:
        return cls._esc(
            f"📦 目標文章數：{event.total}\n"
            f"✅ 補做成功：{event.succeeded}\n"
            f"❌ 補做失敗：{event.failed}"
        )
