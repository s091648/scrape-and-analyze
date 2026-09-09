from src.infrastructure.shared.notifications.job_completion_message_builder import JobCompletionMessageBuilder
from src.modules.collection.application.events import PipelineCompletedEvent


class PipelineCompletedMessageBuilder(JobCompletionMessageBuilder):
    """Builds a MarkdownV2 TelegramMessage describing a scraper pipeline completion event."""

    _emoji = "🤖"
    _title = "Scraping"
    _failure_noun = "個錯誤"

    @classmethod
    def _failed_count(cls, event: PipelineCompletedEvent) -> int:
        """Hard failures only — articles that couldn't even be scraped/saved.
        Downstream-stage failures are reported separately (partial failures)."""
        return sum(r.failed for r in event.stats)

    @classmethod
    def _partial_failure_count(cls, event: PipelineCompletedEvent) -> int:
        """Articles that were saved but a later stage (analysis / tag
        normalization / translation / RAG ingestion) failed."""
        return getattr(event, "partial_failure_count", 0) or 0

    @classmethod
    def _render_footer(cls, event: PipelineCompletedEvent) -> str:
        failed = cls._failed_count(event)
        partial = cls._partial_failure_count(event)
        if failed > 0:
            text = f"⚠ 有 {failed} {cls._failure_noun}"
            if partial > 0:
                text += f"，另有 {partial} 篇部分失敗"
            text += "，請檢查 log"
        elif partial > 0:
            text = f"⚠ 有 {partial} 篇部分失敗（後續步驟），請檢查 log"
        else:
            text = "✅ 全部完成"
        return cls._esc(text)

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

        plain_lines = [f"📦 來源數：{len(results)}"]
        partial = cls._partial_failure_count(event)
        if partial > 0:
            plain_lines.append(f"⚠️ 部分失敗（分析/翻譯/RAG 等後續步驟）：{partial} 篇")
        rag_skipped = getattr(event, "rag_rate_limited_skipped", 0) or 0
        if rag_skipped > 0:
            plain_lines.append(
                f"🚫 RAG 當日額度（RPD）用罄，{rag_skipped} 篇本輪跳過（backfill 補做）"
            )
        if event.rate_limited_hosts:
            plain_lines.append(f"🚫 爬蟲來源已限流本次略過：{'、'.join(event.rate_limited_hosts)}")
        if event.rate_limited_llm_providers:
            plain_lines.append(f"🚫 LLM provider 已限流：{'、'.join(event.rate_limited_llm_providers)}")
        plain = cls._esc("\n".join(plain_lines))
        return f"{plain}\n\n```\n{table}\n```"
