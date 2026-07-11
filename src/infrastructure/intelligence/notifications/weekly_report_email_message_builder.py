from dataclasses import dataclass

from src.modules.intelligence.application.notifications import (
    build_weekly_report_notification_content,
)
from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport

_EN_SUBJECT = "Your Weekly Report is Ready"
_ZH_SUBJECT = "您的每週報告已準備好"


@dataclass(frozen=True)
class EmailMessage:
    """Transport-agnostic representation of a weekly report email to be sent."""

    subject: str
    html: str


class WeeklyReportEmailMessageBuilder:
    """Builds an HTML EmailMessage describing a completed weekly report.

    Mirrors WeeklyReportTelegramMessageBuilder: shares the same channel-agnostic
    WeeklyReportNotificationContent, only the rendering differs per channel.
    """

    @staticmethod
    def build(report: WeeklyReport, locale: str, site_url: str) -> EmailMessage:
        """Return an EmailMessage announcing *report* to a subscriber with *locale*."""
        content = build_weekly_report_notification_content(
            report, locale=locale, site_url=site_url
        )
        subject = _ZH_SUBJECT if locale == "zh-TW" else _EN_SUBJECT
        cover_style = (
            f'background-image: url("{content.cover_image_url}"); background-size: cover; background-position: center;'
            if content.cover_image_url
            else "background-color: #1a1a2e;"
        )
        html = f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;font-family:sans-serif;background:#f5f5f5;">
  <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;">
    <div style="{cover_style}min-height:200px;display:flex;align-items:flex-end;">
      <div style="background:rgba(255,255,255,0.85);margin:16px;padding:16px;border-radius:6px;width:calc(100% - 64px);">
        <h1 style="margin:0 0 8px;font-size:20px;color:#111;">{content.title}</h1>
        <p style="margin:0;font-size:14px;color:#444;">{content.summary_excerpt}...</p>
        <a href="{content.cta_url}" style="display:inline-block;margin-top:12px;padding:8px 18px;background:#111;color:#fff;border-radius:4px;text-decoration:none;font-size:13px;">{content.cta_label}</a>
      </div>
    </div>
  </div>
</body>
</html>"""
        return EmailMessage(subject=subject, html=html)


__all__ = ["WeeklyReportEmailMessageBuilder", "EmailMessage"]
