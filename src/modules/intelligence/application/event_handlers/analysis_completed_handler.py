from opentelemetry import trace as _otel_trace
from opentelemetry.trace import StatusCode

from shared.enums.observability import SpanName
from shared.observability.traceback_filter import format_filtered_exc
from src.shared.logging import get_logger
from src.modules.intelligence.application.events import (
    AnalysisCompletedEvent,
    TranslationFailedEvent,
)
from src.modules.intelligence.application.use_cases.translate_article import AsyncTranslateArticleUseCase
from src.modules.intelligence.application.use_cases.translate_tags import AsyncTranslateTagsUseCase
from src.modules.intelligence.application.use_cases.translate_article_body import AsyncTranslateArticleBodyUseCase
from src.modules.intelligence.domain.repositories import AsyncAnalysesTranslationRepository
from src.shared.domain.repositories import AsyncArticleRepository

logger = get_logger(__name__)
_tracer = _otel_trace.get_tracer(__name__)


class AnalysisCompletedHandler:
    """Translates article analysis, article body, and tags after analysis completes.

    024-async-pipeline-refactor: converted to async in place — confirmed
    constructed only once, only inside build_collection_pipeline(). Takes the
    new Async* translate use cases and AsyncAnalysesTranslationRepository.

    fix/sanitize: dispatched independently off AnalysisCompletedEvent now
    (fan-out, via CollectionPipeline's Barrier 1.5 — see
    CollectionPipeline._dispatch_translation), not chained after
    TagNormalizationCompletedEvent — tag normalization failing/being slow no
    longer blocks translation. Since it no longer receives article_title/
    article_content relayed through that event, it fetches the article body
    itself via article_repo.
    """

    def __init__(
        self,
        translate_article_uc: AsyncTranslateArticleUseCase,
        translate_tags_uc: AsyncTranslateTagsUseCase,
        translate_body_uc: AsyncTranslateArticleBodyUseCase,
        analyses_translation_repo: AsyncAnalysesTranslationRepository,
        article_repo: AsyncArticleRepository,
        event_bus,
        target_languages: list[str] | None = None,
    ) -> None:
        self._translate_article_uc = translate_article_uc
        self._translate_tags_uc = translate_tags_uc
        self._translate_body_uc = translate_body_uc
        self._analyses_translation_repo = analyses_translation_repo
        self._article_repo = article_repo
        self._event_bus = event_bus
        self._target_languages = target_languages or ["zh-TW"]

    async def handle(self, event: AnalysisCompletedEvent) -> None:
        """Translate article analysis, body, and tags for each configured target language.

        024-async-pipeline-refactor follow-up: owns its own span
        (article.analysis_completed.handle — "Analysis Done" in the admin
        waterfall) instead of relying on a bootstrap-level with_span wrapper
        that no longer exists. Unlike ArticleScrapedHandler/etc, the inner
        per-language article.translate.handle spans are meant to stay nested
        children here (not deferred into siblings) — this handler doesn't
        hand off to another pipeline-stage handler, so there's no downstream
        sibling span to protect from over-nesting.
        """
        with _tracer.start_as_current_span(SpanName.ANALYSIS_COMPLETED_HANDLE) as span:
            span.set_attribute("analysis.id", str(event.analysis_id))
            span.set_attribute("article.id", str(event.article_id))
            span.set_attribute("translation.target_languages", ", ".join(self._target_languages))
            if event.topic_id:
                span.set_attribute("article.topic_id", str(event.topic_id))

            try:
                article_title, article_content = await self._fetch_article_body(event.article_id)
            except Exception as e:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, type(e).__name__)
                logger.exception(
                    "article_body_fetch_failed",
                    article_id=str(event.article_id), error=str(e), error_type=type(e).__name__,
                )
                article_title, article_content = None, None
                await self._event_bus.publish(TranslationFailedEvent(
                    analysis_id=event.analysis_id,
                    article_id=event.article_id,
                    task_type="translate_article_body",
                    exception_type=type(e).__name__,
                    exception_message=str(e),
                    traceback=format_filtered_exc(e),
                ))

            try:
                en_content = await self._analyses_translation_repo.find_by_analysis_id_and_language(
                    event.analysis_id, 'en'
                )
            except Exception as e:
                # Roll back so this shared session stays usable for whatever runs
                # next on it (body/tag translation below, and FailedTaskPersistenceHandler
                # itself) — an un-rolled-back failure here would otherwise silently
                # lose every failure record this handler publishes afterward
                # (CodeRabbit review, 026-rate-limit-codegen PR #127).
                span.record_exception(e)
                logger.exception(
                    "english_content_lookup_failed",
                    analysis_id=str(event.analysis_id), error=str(e), error_type=type(e).__name__,
                )
                await self._analyses_translation_repo.rollback()
                en_content = None
                await self._event_bus.publish(TranslationFailedEvent(
                    analysis_id=event.analysis_id,
                    article_id=event.article_id,
                    task_type="translate_article",
                    exception_type=type(e).__name__,
                    exception_message=str(e),
                    traceback=format_filtered_exc(e),
                ))

            if not en_content:
                logger.warning("no_english_content_found", analysis_id=str(event.analysis_id))

            for lang in self._target_languages:
                with _tracer.start_as_current_span("article.translate.handle") as lang_span:
                    lang_span.set_attribute("translation.language", lang)
                    lang_span.set_attribute("analysis.id", str(event.analysis_id))
                    lang_span.set_attribute("article.id", str(event.article_id))

                    # ── Analysis translation (skipped if English content missing) ──
                    if en_content:
                        try:
                            await self._translate_article_uc.execute(
                                analysis_id=event.analysis_id,
                                summary=en_content.summary,
                                pain_points=en_content.pain_points,
                                insights=en_content.insights,
                                innovations=en_content.innovations,
                                target_language=lang,
                            )
                            lang_span.set_attribute("translation.success", True)
                            logger.info("auto_translation_completed", analysis_id=str(event.analysis_id), language=lang)
                        except Exception as e:
                            lang_span.set_attribute("translation.success", False)
                            lang_span.record_exception(e)
                            lang_span.set_status(StatusCode.ERROR, type(e).__name__)
                            logger.exception(
                                "auto_translation_error",
                                analysis_id=str(event.analysis_id), language=lang,
                                error=str(e), error_type=type(e).__name__,
                            )
                            await self._event_bus.publish(TranslationFailedEvent(
                                analysis_id=event.analysis_id,
                                article_id=event.article_id,
                                task_type="translate_article",
                                exception_type=type(e).__name__,
                                exception_message=str(e),
                                traceback=format_filtered_exc(e),
                                context={"language": lang},
                            ))

                    # ── Article body translation (title + content) — skipped if the
                    # article body fetch above failed (already reported once, not
                    # per-language) ─────────────────────────────────────────────
                    if article_title is not None:
                        try:
                            await self._translate_body_uc.execute(
                                article_id=event.article_id,
                                title=article_title,
                                content=article_content,
                                target_language=lang,
                            )
                            logger.info("auto_body_translation_completed", article_id=str(event.article_id), language=lang)
                        except Exception as e:
                            lang_span.record_exception(e)
                            lang_span.set_status(StatusCode.ERROR, type(e).__name__)
                            logger.exception(
                                "auto_body_translation_error",
                                article_id=str(event.article_id), language=lang,
                                error=str(e), error_type=type(e).__name__,
                            )
                            await self._event_bus.publish(TranslationFailedEvent(
                                analysis_id=event.analysis_id,
                                article_id=event.article_id,
                                task_type="translate_article_body",
                                exception_type=type(e).__name__,
                                exception_message=str(e),
                                traceback=format_filtered_exc(e),
                                context={"language": lang},
                            ))

                    # ── Tag & group translation ───────────────────────────────────
                    try:
                        await self._translate_tags_uc.translate_tags(lang, limit=50)
                    except Exception as e:
                        lang_span.record_exception(e)
                        lang_span.set_status(StatusCode.ERROR, type(e).__name__)
                        logger.exception(
                            "auto_tag_translation_error",
                            language=lang, error=str(e), error_type=type(e).__name__,
                        )
                        await self._event_bus.publish(TranslationFailedEvent(
                            analysis_id=event.analysis_id,
                            article_id=event.article_id,
                            task_type="translate_tags",
                            exception_type=type(e).__name__,
                            exception_message=str(e),
                            traceback=format_filtered_exc(e),
                            context={"language": lang},
                        ))

                    try:
                        await self._translate_tags_uc.translate_groups(lang, limit=50)
                    except Exception as e:
                        lang_span.record_exception(e)
                        lang_span.set_status(StatusCode.ERROR, type(e).__name__)
                        logger.exception(
                            "auto_group_translation_error",
                            language=lang, error=str(e), error_type=type(e).__name__,
                        )
                        await self._event_bus.publish(TranslationFailedEvent(
                            analysis_id=event.analysis_id,
                            article_id=event.article_id,
                            task_type="translate_groups",
                            exception_type=type(e).__name__,
                            exception_message=str(e),
                            traceback=format_filtered_exc(e),
                            context={"language": lang},
                        ))

    async def _fetch_article_body(self, article_id) -> tuple[str, str]:
        """Fetch article title and content from the database.

        Raises on DB failure so the caller can publish a TranslationFailedEvent
        and skip only the body translation, without aborting analysis/tag
        translation (which don't need the article body at all).
        """
        article = await self._article_repo.find_by_id(article_id)
        if article:
            return article.title or "", article.content or ""
        return "", ""
