import os
from typing import Optional
from uuid import UUID

from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport
from src.shared.logging import get_logger

logger = get_logger(__name__)

_EN_SUBJECT = "Your Weekly Report is Ready"
_ZH_SUBJECT = "您的每週報告已準備好"
_EN_CTA = "View Full Report"
_ZH_CTA = "查看完整報告"


def _build_html(report: WeeklyReport, locale: str, site_url: str) -> str:
    subject_cta = _ZH_CTA if locale == "zh-TW" else _EN_CTA
    cover_style = (
        f'background-image: url("{report.cover_image_url}"); background-size: cover; background-position: center;'
        if report.cover_image_url
        else "background-color: #1a1a2e;"
    )
    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;font-family:sans-serif;background:#f5f5f5;">
  <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;">
    <div style="{cover_style}min-height:200px;display:flex;align-items:flex-end;">
      <div style="background:rgba(255,255,255,0.85);margin:16px;padding:16px;border-radius:6px;width:calc(100% - 64px);">
        <h1 style="margin:0 0 8px;font-size:20px;color:#111;">{report.title}</h1>
        <p style="margin:0;font-size:14px;color:#444;">{report.summary_text[:300]}...</p>
        <a href="{site_url}" style="display:inline-block;margin-top:12px;padding:8px 18px;background:#111;color:#fff;border-radius:4px;text-decoration:none;font-size:13px;">{subject_cta}</a>
      </div>
    </div>
  </div>
</body>
</html>"""


class WeeklyReportEmailNotifier:
    def __init__(self, session, api_key: str, from_email: str, site_url: str = "") -> None:
        self._session = session
        self._api_key = api_key
        self._from_email = from_email
        self._site_url = site_url or os.environ.get("FRONTEND_ORIGIN", "https://example.com")

    def notify(self, report: WeeklyReport, topic_id: Optional[UUID] = None) -> None:
        import resend
        from models.user_subscription import UserTopicSubscription, UserNotificationSettings

        resend.api_key = self._api_key

        if not topic_id:
            return

        subs = (
            self._session.query(UserTopicSubscription, UserNotificationSettings)
            .join(UserNotificationSettings, UserNotificationSettings.user_id == UserTopicSubscription.user_id)
            .filter(
                UserTopicSubscription.topic_id == topic_id,
                UserNotificationSettings.email_enabled == True,
            )
            .all()
        )

        from models.user import User
        for sub, settings in subs:
            user = self._session.query(User).filter(User.id == sub.user_id).first()
            if not user or not user.email:
                continue
            locale = settings.locale or "en"
            subject = _ZH_SUBJECT if locale == "zh-TW" else _EN_SUBJECT
            html = _build_html(report, locale, self._site_url)
            try:
                resend.Emails.send({
                    "from": self._from_email,
                    "to": user.email,
                    "subject": subject,
                    "html": html,
                })
                logger.info("weekly_report_email_sent", user_id=str(sub.user_id))
            except Exception as e:
                logger.warning("weekly_report_email_send_failed", user_id=str(sub.user_id), error=str(e))
