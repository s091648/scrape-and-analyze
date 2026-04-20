import re
import requests
from datetime import datetime, timezone

from src.infrastructure.notifications.base import BaseNotifier
from src.infrastructure.observability.run_summary import RunSummary
from src.infrastructure.shared.logging import get_logger

logger = get_logger(__name__)


def _esc(s: str) -> str:
    """Escape special characters for Telegram MarkdownV2 (outside code blocks)."""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', s)


class TelegramNotifier(BaseNotifier):
    def __init__(self, token: str, chat_id: str) -> None:
        self._token = token
        self._chat_id = chat_id

    def send_scrape_summary(self, summary: RunSummary, duration: float) -> None:
        text = self._format_message(summary, duration)
        response = requests.post(
            f"https://api.telegram.org/bot{self._token}/sendMessage",
            json={"chat_id": self._chat_id, "text": text, "parse_mode": "MarkdownV2"},
            timeout=10,
        )
        if not response.ok:
            logger.error(
                "telegram_send_failed",
                status_code=response.status_code,
                response_body=response.text[:500],
            )
        response.raise_for_status()

    def _format_message(self, summary: RunSummary, duration: float) -> str:
        results = summary.get_results()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # Build table (inside code block — no escaping needed)
        col_w = max((len(r.source) for r in results), default=10) + 2
        header = f"{'來源':<{col_w}} {'新增':>5} {'重複':>5} {'失敗':>5}"
        sep = "─" * (col_w + 19)
        rows = []
        for r in results:
            flag = " ⚠" if r.failed > 0 else ""
            rows.append(f"{r.source:<{col_w}} {r.new:>5} {r.duplicate:>5} {r.failed:>5}{flag}")
        total_row = (
            f"{'合計':<{col_w}} "
            f"{summary.total_new():>5} "
            f"{summary.total_duplicate():>5} "
            f"{summary.total_failed():>5}"
        )
        table = "\n".join([header, sep] + rows + [sep, total_row])

        footer = (
            f"⚠ 有 {summary.total_failed()} 個錯誤，請檢查 log"
            if summary.total_failed() > 0
            else "✅ 全部完成"
        )

        plain = _esc(
            f"🤖 Scraping 任務完成\n\n"
            f"📅 {now}\n"
            f"⏱ 耗時：{duration:.1f} 秒\n"
            f"📦 來源數：{len(results)}"
        )

        return f"{plain}\n\n```\n{table}\n```\n\n{_esc(footer)}"
