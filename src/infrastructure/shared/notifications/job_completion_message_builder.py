"""Base class for MarkdownV2 Telegram messages summarizing a scheduled CLI job's
completion. Owns the parts every job-completion notification shares — the escaped
header (timestamp, non-production environment badge, execution window, duration,
jitter) and the success/failure footer — so each job's message builder only needs
to supply its emoji/title/failure-noun and its own detail lines.

020-redis-caching-layer follow-up: unifies notification format across main.py /
refresh_metrics.py / backfill_rag.py / weekly_report.py / dedup_reconcile.py.
"""
import re
from abc import ABC, abstractmethod
from typing import Any

from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta
from src.shared.domain.value_objects.telegram_message import TelegramMessage


class JobCompletionMessageBuilder(ABC):
    """Subclass and set `_emoji` / `_title` / `_failure_noun`, then implement
    `_failed_count()` and `_render_body()`. `build()` assembles header + body + footer."""

    _emoji: str
    _title: str
    _failure_noun: str  # e.g. "篇更新失敗" — used in the failure footer line

    @staticmethod
    def _esc(s: str) -> str:
        """Escape MarkdownV2 special characters in a string."""
        return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', s)

    @classmethod
    def build(cls, event: Any) -> TelegramMessage:
        """Format and return a TelegramMessage for the given job-completion event."""
        header = cls._render_header(event.execution)
        body = cls._render_body(event)
        footer = cls._render_footer(event)
        return TelegramMessage(text=f"{header}\n\n{body}\n\n{footer}", parse_mode="MarkdownV2")

    @classmethod
    def _render_header(cls, meta: JobExecutionMeta) -> str:
        """Timestamp + non-production environment badge + execution window + duration + jitter."""
        lines = [f"{cls._emoji} {cls._title} 任務完成", ""]
        lines.append(f"📅 {meta.completed_at.strftime('%Y-%m-%d %H:%M UTC')}")
        if meta.app_env.lower() != "production":
            lines.append(f"🌐 環境：{meta.app_env}")
        lines.append(
            f"🕐 執行區間：{meta.started_at.strftime('%H:%M:%S')}–{meta.completed_at.strftime('%H:%M:%S')} UTC"
        )
        lines.append(f"⏱ 耗時：{meta.duration_seconds:.1f} 秒")
        if meta.jitter_seconds is not None:
            lines.append(f"🎲 啟動 jitter：{meta.jitter_seconds:.1f} 秒")
        return cls._esc("\n".join(lines))

    @classmethod
    def _render_footer(cls, event: Any) -> str:
        failed = cls._failed_count(event)
        text = f"⚠ 有 {failed} {cls._failure_noun}，請檢查 log" if failed > 0 else "✅ 全部完成"
        return cls._esc(text)

    @classmethod
    @abstractmethod
    def _failed_count(cls, event: Any) -> int:
        ...

    @classmethod
    @abstractmethod
    def _render_body(cls, event: Any) -> str:
        """Return the already-MarkdownV2-escaped detail block (counts, tables, etc.)."""
        ...
