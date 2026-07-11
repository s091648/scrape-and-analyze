"""Weekly report email notifier — orchestrates DB query + content build + transport send.

This module is intentionally thin: it does not format messages (that lives in
WeeklyReportEmailMessageBuilder) and does not know Resend's API shape beyond
the minimal send() call.
"""
from dataclasses import replace
from typing import Dict, Optional
from uuid import UUID

from src.config.settings import FRONTEND_ORIGIN
from src.infrastructure.intelligence.notifications.weekly_report_email_message_builder import (
    WeeklyReportEmailMessageBuilder,
)
from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport
from src.shared.logging import get_logger

logger = get_logger(__name__)


class WeeklyReportEmailNotifier:
    def __init__(self, session, api_key: str, from_email: str, site_url: str = "") -> None:
        self._session = session
        self._api_key = api_key
        self._from_email = from_email
        self._site_url = site_url or FRONTEND_ORIGIN

    def _localize(self, report: WeeklyReport, language: str, cache: Dict[str, WeeklyReport]) -> WeeklyReport:
        """Return *report* with title/summary_text swapped for the translated copy in *language*."""
        if language == "en" or report.id is None:
            return report
        if language not in cache:
            from models.weekly_report_translation import WeeklyReportTranslation

            row = (
                self._session.query(WeeklyReportTranslation)
                .filter(
                    WeeklyReportTranslation.weekly_report_id == report.id,
                    WeeklyReportTranslation.language == language,
                )
                .first()
            )
            cache[language] = (
                replace(report, title=row.title, summary_text=row.summary_text) if row else report
            )
        return cache[language]

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
        translation_cache: Dict[str, WeeklyReport] = {}
        for sub, settings in subs:
            user = self._session.query(User).filter(User.id == sub.user_id).first()
            if not user or not user.email:
                continue
            locale = settings.locale or "en"
            localized_report = self._localize(report, locale, translation_cache)
            message = WeeklyReportEmailMessageBuilder.build(localized_report, locale, self._site_url)
            try:
                resend.Emails.send({
                    "from": self._from_email,
                    "to": user.email,
                    "subject": message.subject,
                    "html": message.html,
                })
                logger.info("weekly_report_email_sent", user_id=str(sub.user_id))
            except Exception as e:
                logger.warning("weekly_report_email_send_failed", user_id=str(sub.user_id), error=str(e))
