import os
from typing import Optional
from uuid import UUID

from src.infrastructure.shared.notifications.telegram_client import send_telegram_message
from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport
from src.modules.intelligence.domain.value_objects.weekly_report_notification_content import (
    build_weekly_report_notification_content,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


class WeeklyReportTelegramNotifier:
    def __init__(self, session, bot_token: str, site_url: str = "") -> None:
        self._session = session
        self._bot_token = bot_token
        self._site_url = site_url or os.environ.get("FRONTEND_ORIGIN", "https://example.com")

    def notify(self, report: WeeklyReport, topic_id: Optional[UUID] = None) -> None:
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
            content = build_weekly_report_notification_content(
                report, locale=settings.locale or "en", site_url=self._site_url
            )
            message = (
                f"📊 *Weekly Report Ready*\n\n"
                f"*{content.title}*\n\n"
                f"{content.summary_excerpt}...\n\n"
                f"[{content.cta_label}]({content.cta_url})"
            )
            try:
                send_telegram_message(self._bot_token, settings.telegram_chat_id, message, parse_mode="Markdown")
                logger.info("weekly_report_telegram_sent", user_id=str(sub.user_id))
            except Exception as e:
                logger.warning("weekly_report_telegram_send_failed", user_id=str(sub.user_id), error=str(e))
