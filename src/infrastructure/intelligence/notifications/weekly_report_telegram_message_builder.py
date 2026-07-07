from uuid import UUID

from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport
from src.modules.intelligence.domain.value_objects.weekly_report_notification_content import (
    build_weekly_report_notification_content,
)
from src.shared.domain.value_objects.telegram_message import TelegramMessage


class WeeklyReportTelegramMessageBuilder:
    """Builds a Markdown TelegramMessage describing a completed weekly report.

    The builder does not know about Telegram chat ids or the bot client —
    callers (e.g. WeeklyReportTelegramNotifier) wire those after the message
    is built. This keeps message formatting a pure function of (report, locale).
    """

    @staticmethod
    def build(report: WeeklyReport, locale: str, site_url: str) -> TelegramMessage:
        """Return a TelegramMessage announcing *report* to a subscriber with *locale*."""
        content = build_weekly_report_notification_content(
            report, locale=locale, site_url=site_url
        )
        text = (
            f"📊 *Weekly Report Ready*\n\n"
            f"*{content.title}*\n\n"
            f"{content.summary_excerpt}...\n\n"
            f"[{content.cta_label}]({content.cta_url})"
        )
        return TelegramMessage(text=text, parse_mode="Markdown")


__all__ = ["WeeklyReportTelegramMessageBuilder"]
