import os
import requests
from typing import Optional
from uuid import UUID

from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport
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
            chat_id = settings.telegram_chat_id
            message = (
                f"📊 *Weekly Report Ready*\n\n"
                f"*{report.title}*\n\n"
                f"{report.summary_text[:300]}...\n\n"
                f"[{('查看完整報告' if settings.locale == 'zh-TW' else 'View Full Report')}]({self._site_url})"
            )
            try:
                response = requests.post(
                    f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
                    timeout=10,
                )
                response.raise_for_status()
                logger.info("weekly_report_telegram_sent", user_id=str(sub.user_id))
            except Exception as e:
                logger.warning("weekly_report_telegram_send_failed", user_id=str(sub.user_id), error=str(e))
