from src.infrastructure.shared.notifications.job_completion_message_builder import JobCompletionMessageBuilder
from src.modules.intelligence.application.events import WeeklyReportJobCompletedEvent


class WeeklyReportJobCompletedMessageBuilder(JobCompletionMessageBuilder):
    """Builds a MarkdownV2 TelegramMessage describing a weekly_report.py job-level
    completion event — the operator-facing "did the job itself run cleanly" summary,
    distinct from the per-report email/telegram notifications sent to subscribers for
    each generated report."""

    _emoji = "🗞️"
    _title = "Weekly Report"
    _failure_noun = "個 topic 生成失敗"

    @classmethod
    def _failed_count(cls, event: WeeklyReportJobCompletedEvent) -> int:
        return event.failed

    @classmethod
    def _render_body(cls, event: WeeklyReportJobCompletedEvent) -> str:
        lines = [
            f"📦 處理 topic 數：{event.total_topics}",
            f"✅ 生成成功：{event.generated}",
            f"❌ 生成失敗：{event.failed}",
        ]
        if event.rate_limited_providers:
            providers = "、".join(event.rate_limited_providers)
            lines.append(f"🚫 LLM provider 已限流：{providers}")
        return cls._esc("\n".join(lines))
