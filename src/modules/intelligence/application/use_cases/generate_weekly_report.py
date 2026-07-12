import json
import uuid
from collections import Counter
from datetime import date, datetime, timezone
from typing import Iterable, List, Optional
from uuid import UUID

from opentelemetry import trace as _otel_trace
from opentelemetry.trace import StatusCode

from shared.enums.observability import SERVICE_NAME, SpanName
from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport
from src.modules.intelligence.domain.entities.weekly_report_translation import WeeklyReportTranslation
from src.modules.intelligence.domain.repositories.weekly_report_repository import WeeklyReportRepository
from src.modules.intelligence.domain.repositories.weekly_report_translation_repository import WeeklyReportTranslationRepository
from src.modules.intelligence.domain.services.text_generation_service import TextGenerationService
from src.modules.intelligence.domain.services.image_generation_service import ImageGenerationService
from src.modules.intelligence.domain.value_objects import WeeklyReportTranslationPrompt
from src.modules.intelligence.domain.value_objects.image_generation_prompt import ImageGenerationPrompt
from src.modules.intelligence.domain.value_objects.weekly_report_prompt import WeeklyReportPrompt
from src.shared.domain.services.blob_storage_service import BlobStorageService
from src.shared.logging import get_logger

logger = get_logger(__name__)


class GenerateWeeklyReportUseCase:
    def __init__(
        self,
        report_repo: WeeklyReportRepository,
        llm_service: TextGenerationService,
        image_service: ImageGenerationService,
        blob_storage: BlobStorageService,
        translation_repository: WeeklyReportTranslationRepository,
        translation_prompt: WeeklyReportTranslationPrompt,
        email_notifier=None,
        telegram_notifier=None,
        translation_languages: Iterable[str] = (),
    ) -> None:
        self._repo = report_repo
        self._llm = llm_service
        self._image = image_service
        self._blob = blob_storage
        self._translation_repo = translation_repository
        self._translation_prompt = translation_prompt
        self._email = email_notifier
        self._telegram = telegram_notifier
        self._translation_languages = list(translation_languages)

    def execute(self, topic_id: UUID, topic_name: str, week_start: date, force: bool = False) -> WeeklyReport:
        logger.info("weekly_report_generation_started", topic_id=str(topic_id), week_start=str(week_start))
        # Attributes on the weekly_report.topic span opened by WeeklyReportPipeline.run().
        span = _otel_trace.get_current_span()

        if not force:
            existing = self._repo.find_by_topic_and_week(topic_id, week_start)
            if existing and existing.status == "completed":
                span.set_attribute("weekly_report.outcome", "skipped_existing")
                logger.warning(
                    "weekly_report_already_exists_skipped",
                    topic_id=str(topic_id),
                    week_start=str(week_start),
                    report_id=str(existing.id),
                )
                return existing

        articles = self._repo.fetch_top_articles(topic_id, week_start)
        if not articles:
            span.set_attribute("weekly_report.outcome", "no_articles")
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

        span.set_attribute("weekly_report.article_count", len(articles))

        all_tags: List[str] = [tag for a in articles for tag in a.tags]
        top_tags = [tag for tag, _ in Counter(all_tags).most_common(8)]

        prompt = WeeklyReportPrompt().render(
            topic_name=topic_name,
            articles=articles,
            week_start=week_start,
        )

        tracer = _otel_trace.get_tracer(SERVICE_NAME)

        with tracer.start_as_current_span(SpanName.WEEKLY_REPORT_SUMMARIZE) as sub_span:
            try:
                llm_response = self._llm.generate(prompt.content)
                parsed = json.loads(llm_response)
                title = parsed.get("title", f"{topic_name} Weekly Report")
                summary_text = parsed.get("summary_text", "")
                sub_span.set_attribute("weekly_report.summarize.success", True)
            except Exception as e:
                sub_span.set_attribute("weekly_report.summarize.success", False)
                sub_span.set_attribute("weekly_report.summarize.error_type", type(e).__name__)
                sub_span.set_status(StatusCode.ERROR, str(e))
                logger.error("weekly_report_llm_failed", error=str(e))
                title = f"{topic_name} Weekly Report"
                summary_text = ""

        cover_image_url: Optional[str] = None
        with tracer.start_as_current_span(SpanName.WEEKLY_REPORT_IMAGE) as sub_span:
            try:
                week_label = week_start.strftime("%B %d, %Y")
                img_prompt = ImageGenerationPrompt().render(
                    topic_name=topic_name,
                    top_tags=top_tags,
                    week_label=week_label,
                    summary_text=summary_text,
                )
                img_bytes = self._image.generate_image(img_prompt.content)
                key = f"weekly-reports/{topic_id}/{week_start.isoformat()}.png"
                cover_image_url = self._blob.upload(img_bytes, key, "image/png")
                sub_span.set_attribute("weekly_report.image.success", True)
            except Exception as e:
                sub_span.set_attribute("weekly_report.image.success", False)
                sub_span.set_attribute("weekly_report.image.error_type", type(e).__name__)
                sub_span.set_status(StatusCode.ERROR, str(e))
                logger.warning("weekly_report_image_failed", error=str(e))

        article_ids = [str(a.article_id) for a in articles]

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
        span.set_attribute("weekly_report.outcome", "generated")

        for language in self._translation_languages:
            self._translate_report(saved, language)

        if self._email:
            with tracer.start_as_current_span(SpanName.WEEKLY_REPORT_NOTIFY) as sub_span:
                sub_span.set_attribute("notify.channel", "email")
                try:
                    self._email.notify(saved, topic_id=topic_id)
                    sub_span.set_attribute("notify.success", True)
                except Exception as e:
                    sub_span.set_attribute("notify.success", False)
                    sub_span.set_attribute("notify.error_type", type(e).__name__)
                    sub_span.set_status(StatusCode.ERROR, str(e))
                    logger.warning("weekly_report_email_failed", error=str(e))

        if self._telegram:
            with tracer.start_as_current_span(SpanName.WEEKLY_REPORT_NOTIFY) as sub_span:
                sub_span.set_attribute("notify.channel", "telegram")
                try:
                    self._telegram.notify(saved, topic_id=topic_id)
                    sub_span.set_attribute("notify.success", True)
                except Exception as e:
                    sub_span.set_attribute("notify.success", False)
                    sub_span.set_attribute("notify.error_type", type(e).__name__)
                    sub_span.set_status(StatusCode.ERROR, str(e))
                    logger.warning("weekly_report_telegram_failed", error=str(e))

        logger.info("weekly_report_generation_complete", report_id=str(saved.id))
        return saved

    def _translate_report(self, report: WeeklyReport, language: str) -> None:
        """Translate title + summary_text into *language* and persist. Failures are logged, never raised."""
        tracer = _otel_trace.get_tracer(SERVICE_NAME)
        with tracer.start_as_current_span(SpanName.WEEKLY_REPORT_TRANSLATE) as span:
            span.set_attribute("translation.language", language)

            def _fail(error_type: str, message: str) -> None:
                span.set_attribute("translation.success", False)
                span.set_attribute("translation.error_type", error_type)
                span.set_status(StatusCode.ERROR, message)

            if report.id is None:
                _fail("MissingReportId", "report has no id")
                return
            try:
                rendered = self._translation_prompt.render(
                    target_language=language,
                    title=report.title,
                    summary=report.summary_text,
                )
                translated = self._llm.translate("", rendered.content)
            except Exception as e:
                _fail(type(e).__name__, str(e))
                logger.warning(
                    "weekly_report_translation_llm_failed",
                    report_id=str(report.id),
                    language=language,
                    error=str(e),
                )
                return

            if not translated:
                _fail("EmptyResponse", "translation LLM returned an empty response")
                logger.warning(
                    "weekly_report_translation_empty_response",
                    report_id=str(report.id),
                    language=language,
                )
                return

            title, summary = self._parse_translation_response(translated)
            if not title or not summary:
                _fail("ParseFailed", "failed to parse translation response")
                logger.warning(
                    "weekly_report_translation_parse_failed",
                    report_id=str(report.id),
                    language=language,
                )
                return

            original_citations = self._extract_citation_numbers(report.summary_text)
            translated_citations = self._extract_citation_numbers(summary)
            if translated_citations != original_citations:
                logger.warning(
                    "weekly_report_translation_citation_mismatch",
                    report_id=str(report.id),
                    language=language,
                    original_citations=sorted(original_citations),
                    translated_citations=sorted(translated_citations),
                )
                summary = report.summary_text

            try:
                self._translation_repo.save(WeeklyReportTranslation(
                    weekly_report_id=report.id,
                    language=language,
                    title=title,
                    summary_text=summary,
                ))
                span.set_attribute("translation.success", True)
                logger.info(
                    "weekly_report_translated",
                    report_id=str(report.id),
                    language=language,
                )
            except Exception as e:
                _fail(type(e).__name__, str(e))
                logger.warning(
                    "weekly_report_translation_save_failed",
                    report_id=str(report.id),
                    language=language,
                    error=str(e),
                )

    @staticmethod
    def _extract_citation_numbers(text: str) -> set[int]:
        """Return the set of [N] citation marker numbers present in *text*."""
        import re
        return {int(n) for n in re.findall(r'\[(\d+)\]', text)}

    @staticmethod
    def _parse_translation_response(text: str) -> tuple[Optional[str], Optional[str]]:
        """Try JSON first, fall back to section-header parsing."""
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed.get("title"), parsed.get("summary_text")
        except (json.JSONDecodeError, ValueError):
            pass
        return WeeklyReportTranslationPrompt.parse_response(text)
