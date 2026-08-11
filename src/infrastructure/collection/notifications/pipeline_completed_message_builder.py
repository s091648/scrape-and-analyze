from src.infrastructure.shared.notifications.job_completion_message_builder import JobCompletionMessageBuilder
from src.modules.collection.application.events import PipelineCompletedEvent


class PipelineCompletedMessageBuilder(JobCompletionMessageBuilder):
    """Builds a MarkdownV2 TelegramMessage describing a scraper pipeline completion event."""

    _emoji = "🤖"
    _title = "Scraping"
    _failure_noun = "個錯誤"

    @classmethod
    def _failed_count(cls, event: PipelineCompletedEvent) -> int:
        return sum(r.failed for r in event.stats)

    @classmethod
    def _render_body(cls, event: PipelineCompletedEvent) -> str:
        results = event.stats

        col_w = max((len(r.source) for r in results), default=10) + 2
        header = f"{'來源':<{col_w}} {'新增':>5} {'重複':>5} {'失敗':>5}"
        sep = "─" * (col_w + 19)
        rows = []
        for r in results:
            flag = " ⚠" if r.failed > 0 else ""
            rows.append(f"{r.source:<{col_w}} {r.new:>5} {r.duplicate:>5} {r.failed:>5}{flag}")

        total_new = sum(r.new for r in results)
        total_dup = sum(r.duplicate for r in results)
        total_failed = cls._failed_count(event)
        total_row = f"{'合計':<{col_w}} {total_new:>5} {total_dup:>5} {total_failed:>5}"
        table = "\n".join([header, sep] + rows + [sep, total_row])

        plain = cls._esc(f"📦 來源數：{len(results)}")
        return f"{plain}\n\n```\n{table}\n```"
