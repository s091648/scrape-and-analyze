import json
import uuid
from collections import Counter
from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import UUID

from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport
from src.modules.intelligence.domain.repositories.weekly_report_repository import WeeklyReportRepository
from src.modules.intelligence.domain.services.llm_service import LLMService
from src.modules.intelligence.domain.services.image_generation_service import ImageGenerationService
from src.modules.intelligence.domain.services.blob_storage_service import BlobStorageService
from src.modules.intelligence.domain.value_objects.weekly_report_prompt import WeeklyReportPrompt
from src.modules.intelligence.domain.value_objects.image_generation_prompt import ImageGenerationPrompt
from src.shared.logging import get_logger

logger = get_logger(__name__)


class GenerateWeeklyReportUseCase:
    def __init__(
        self,
        report_repo: WeeklyReportRepository,
        llm_service: LLMService,
        image_service: ImageGenerationService,
        blob_storage: BlobStorageService,
        email_notifier=None,
        telegram_notifier=None,
    ) -> None:
        self._repo = report_repo
        self._llm = llm_service
        self._image = image_service
        self._blob = blob_storage
        self._email = email_notifier
        self._telegram = telegram_notifier

    def execute(self, topic_id: UUID, topic_name: str, week_start: date) -> WeeklyReport:
        logger.info("weekly_report_generation_started", topic_id=str(topic_id), week_start=str(week_start))

        articles = self._repo.fetch_top_articles(topic_id, week_start)
        if not articles:
            logger.warning("no_articles_for_weekly_report", topic_id=str(topic_id))
            report = WeeklyReport(
                id=uuid.uuid4(),
                topic_id=topic_id,
                week_start_date=week_start,
                title="No articles this week",
                summary_text="",
                cover_image_url=None,
                article_ids=[],
                article_count=0,
                status="completed",
            )
            return self._repo.save(report)

        all_tags: List[str] = [tag for a in articles for tag in a.tags]
        top_tags = [tag for tag, _ in Counter(all_tags).most_common(8)]

        prompt = WeeklyReportPrompt().render(
            topic_name=topic_name,
            articles=articles,
            week_start=week_start,
        )

        try:
            llm_response = self._llm.analyze(prompt.content)
            parsed = json.loads(llm_response)
            title = parsed.get("title", f"{topic_name} Weekly Report")
            summary_text = parsed.get("summary_text", "")
        except Exception as e:
            logger.error("weekly_report_llm_failed", error=str(e))
            title = f"{topic_name} Weekly Report"
            summary_text = ""

        cover_image_url: Optional[str] = None
        try:
            week_label = week_start.strftime("%B %d, %Y")
            img_prompt = ImageGenerationPrompt().render(
                topic_name=topic_name,
                top_tags=top_tags,
                week_label=week_label,
            )
            img_bytes = self._image.generate_image(img_prompt.content)
            key = f"weekly-reports/{topic_id}/{week_start.isoformat()}.png"
            cover_image_url = self._blob.upload(img_bytes, key, "image/png")
        except Exception as e:
            logger.warning("weekly_report_image_failed", error=str(e))

        article_ids = [str(a.title) for a in articles]

        report = WeeklyReport(
            id=uuid.uuid4(),
            topic_id=topic_id,
            week_start_date=week_start,
            title=title,
            summary_text=summary_text,
            cover_image_url=cover_image_url,
            article_ids=article_ids,
            article_count=len(articles),
            status="completed",
        )
        saved = self._repo.save(report)

        if self._email:
            try:
                self._email.notify(saved, topic_id=topic_id)
            except Exception as e:
                logger.warning("weekly_report_email_failed", error=str(e))

        if self._telegram:
            try:
                self._telegram.notify(saved, topic_id=topic_id)
            except Exception as e:
                logger.warning("weekly_report_telegram_failed", error=str(e))

        logger.info("weekly_report_generation_complete", report_id=str(saved.id))
        return saved
