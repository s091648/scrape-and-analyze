from opentelemetry import trace as _otel_trace

from src.shared.logging import get_logger
from src.modules.intelligence.application.events import (
    TagNormalizationCompletedEvent,
    TranslationFailedEvent,
)
from src.modules.intelligence.application.use_cases import TranslateArticleUseCase, TranslateTagsUseCase
from src.modules.intelligence.application.use_cases.translate_article_body import TranslateArticleBodyUseCase
from src.modules.intelligence.domain.repositories import AnalysesTranslationRepository
from src.shared.application.ports import EventBus

_logger = get_logger(__name__)
_tracer = _otel_trace.get_tracer(__name__)


class AnalysisCompletedHandler:
    """Translates article analysis, article body, and tags after tag normalization completes."""

    def __init__(
        self,
        translate_article_uc: TranslateArticleUseCase,
        translate_tags_uc: TranslateTagsUseCase,
        translate_body_uc: TranslateArticleBodyUseCase,
        analyses_translation_repo: AnalysesTranslationRepository,
        event_bus: EventBus,
        target_languages: list[str] | None = None,
    ) -> None:
        self._translate_article_uc = translate_article_uc
        self._translate_tags_uc = translate_tags_uc
        self._translate_body_uc = translate_body_uc
        self._analyses_translation_repo = analyses_translation_repo
        self._event_bus = event_bus
        self._target_languages = target_languages or ["zh-TW"]

    def handle(self, event: TagNormalizationCompletedEvent) -> None:
        """Translate article analysis, body, and tags for each configured target language."""
        span = _otel_trace.get_current_span()
        span.set_attribute("analysis.id", str(event.analysis_id))
        span.set_attribute("article.id", str(event.article_id))
        span.set_attribute("translation.target_languages", ", ".join(self._target_languages))
        if event.topic_id:
            span.set_attribute("article.topic_id", str(event.topic_id))

        en_content = self._analyses_translation_repo.find_by_analysis_id_and_language(
            event.analysis_id, 'en'
        )
        if not en_content:
            _logger.warning("no_english_content_found", analysis_id=str(event.analysis_id))

        for lang in self._target_languages:
            with _tracer.start_as_current_span("article.translate.handle") as lang_span:
                lang_span.set_attribute("translation.language", lang)
                lang_span.set_attribute("analysis.id", str(event.analysis_id))
                lang_span.set_attribute("article.id", str(event.article_id))

                # ── Analysis translation (skipped if English content missing) ──
                if en_content:
                    try:
                        result = self._translate_article_uc.execute(
                            analysis_id=event.analysis_id,
                            summary=en_content.summary,
                            pain_points=en_content.pain_points,
                            insights=en_content.insights,
                            innovations=en_content.innovations,
                            target_language=lang,
                        )
                        if result.success:
                            lang_span.set_attribute("translation.success", True)
                            _logger.info("auto_translation_completed", analysis_id=str(event.analysis_id), language=lang)
                        else:
                            lang_span.set_attribute("translation.success", False)
                            self._event_bus.publish(TranslationFailedEvent(
                                analysis_id=event.analysis_id,
                                article_id=event.article_id,
                                task_type="translate_article",
                                exception_type="TranslationError",
                                exception_message=f"Translation failed for lang={lang}",
                                context={"language": lang},
                            ))
                    except Exception as e:
                        lang_span.record_exception(e)
                        _logger.error("auto_translation_error", analysis_id=str(event.analysis_id), language=lang, error=str(e))
                        self._event_bus.publish(TranslationFailedEvent(
                            analysis_id=event.analysis_id,
                            article_id=event.article_id,
                            task_type="translate_article",
                            exception_type=type(e).__name__,
                            exception_message=str(e),
                            context={"language": lang},
                        ))

                # ── Article body translation (title + content) ────────────────
                try:
                    body_result = self._translate_body_uc.execute(
                        article_id=event.article_id,
                        title=event.article_title,
                        content=event.article_content,
                        target_language=lang,
                    )
                    if not body_result.success:
                        self._event_bus.publish(TranslationFailedEvent(
                            analysis_id=event.analysis_id,
                            article_id=event.article_id,
                            task_type="translate_article_body",
                            exception_type="TranslationError",
                            exception_message=f"Body translation failed for lang={lang}",
                            context={"language": lang},
                        ))
                    else:
                        _logger.info("auto_body_translation_completed", article_id=str(event.article_id), language=lang)
                except Exception as e:
                    lang_span.record_exception(e)
                    _logger.error("auto_body_translation_error", article_id=str(event.article_id), language=lang, error=str(e))
                    self._event_bus.publish(TranslationFailedEvent(
                        analysis_id=event.analysis_id,
                        article_id=event.article_id,
                        task_type="translate_article_body",
                        exception_type=type(e).__name__,
                        exception_message=str(e),
                        context={"language": lang},
                    ))

                # ── Tag & group translation ───────────────────────────────────
                try:
                    self._translate_tags_uc.translate_tags(lang, limit=50)
                except Exception as e:
                    lang_span.record_exception(e)
                    _logger.error("auto_tag_translation_error", language=lang, error=str(e))

                try:
                    self._translate_tags_uc.translate_groups(lang, limit=50)
                except Exception as e:
                    lang_span.record_exception(e)
                    _logger.error("auto_group_translation_error", language=lang, error=str(e))
