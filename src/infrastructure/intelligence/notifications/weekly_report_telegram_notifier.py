"""Weekly report telegram notifier — orchestrates DB query + content build + transport send.

This module is intentionally thin: it does not format messages (that lives in
WeeklyReportTelegramMessageBuilder) and does not talk to the Telegram API
directly (that lives in the shared TelegramNotifierService / TelegramNotifierClient).
"""
from typing import Optional
from uuid import UUID

from src.config.settings import FRONTEND_ORIGIN
from src.infrastructure.intelligence.notifications.weekly_report_telegram_message_builder import (
    WeeklyReportTelegramMessageBuilder,
)
from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport
from src.shared.domain.services.telegram_notifier_service import TelegramNotifierService
from src.shared.logging import get_logger

logger = get_logger(__name__)


class WeeklyReportTelegramNotifier:
    """Sends a weekly report Telegram message to every subscriber of a topic."""

    def __init__(
        self,
        session,
        notifier: TelegramNotifierService,
        site_url: str = "",
    ) -> None:
        self._session = session
        self._notifier = notifier
        self._site_url = site_url or FRONTEND_ORIGIN

    def notify(self, report: WeeklyReport, topic_id: Optional[UUID] = None) -> None:
        """Send the weekly report to every telegram-enabled subscriber of *topic_id*."""
        from models.user_subscription import UserTopicSubscription, UserNotificationSettings

        if not topic_id:
            return

        subs = (
            self._session.query(UserTopicSubscription, UserNotificationSettings)
            .join(UserNotificationSettings, UserNotificationSettings.user_id == UserTopicSubscription.user_id)
            .filter(
                UserTopicSubscription.topic_id == topic_id,
                UserNotificationSettings.telegram_enabled == True,
                UserNotificationSettings.telegram_chat_id.isnot(None),
            )
            .all()
        )

        for sub, settings in subs:
            message = WeeklyReportTelegramMessageBuilder.build(
                report, locale=settings.locale or "en", site_url=self._site_url
            )
            try:
                self._notifier.send(settings.telegram_chat_id, message)
                logger.info("weekly_report_telegram_sent", user_id=str(sub.user_id))
            except Exception as e:
                logger.warning(
                    "weekly_report_telegram_send_failed",
                    user_id=str(sub.user_id),
                    error=str(e),
                )
