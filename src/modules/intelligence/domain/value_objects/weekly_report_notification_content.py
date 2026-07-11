from dataclasses import dataclass
from typing import Optional

from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport

_EN_CTA = "View Full Report"
_ZH_CTA = "查看完整報告"

_SUMMARY_EXCERPT_LENGTH = 300


@dataclass(frozen=True)
class WeeklyReportNotificationContent:
    """Locale-aware notification copy shared by every channel (Telegram, email, ...)."""

    title: str
    summary_excerpt: str
    cta_label: str
    cta_url: str
    cover_image_url: Optional[str]


def build_weekly_report_deep_link(report: WeeklyReport, site_url: str) -> str:
    """URL to the homepage pre-scrolled to *report*'s week, for notification CTAs."""
    base = site_url.rstrip("/")
    if not report.topic_id:
        return base or site_url
    return f"{base}/?topic={report.topic_id}&week={report.week_start_date.isoformat()}"


def build_weekly_report_notification_content(
    report: WeeklyReport, locale: str, site_url: str
) -> WeeklyReportNotificationContent:
    cta_label = _ZH_CTA if locale == "zh-TW" else _EN_CTA
    return WeeklyReportNotificationContent(
        title=report.title,
        summary_excerpt=report.summary_text[:_SUMMARY_EXCERPT_LENGTH],
        cta_label=cta_label,
        cta_url=build_weekly_report_deep_link(report, site_url),
        cover_image_url=report.cover_image_url,
    )
