"""
Unit tests for AnalysisCompletedHandler — covers auto-translation after
tag normalization, English content prerequisite, failure event publishing,
and tag/group translation error swallowing.
"""
import uuid
from unittest.mock import MagicMock, call, patch

import pytest

from src.modules.intelligence.application.event_handlers.analysis_completed_handler import (
    AnalysisCompletedHandler,
)
from src.modules.intelligence.application.events import (
    TagNormalizationCompletedEvent,
    TranslationFailedEvent,
)
from src.modules.intelligence.domain.value_objects import AnalysesTranslationResult, AnalysesTranslationContent


def _event():
    return TagNormalizationCompletedEvent(
        analysis_id=uuid.uuid4(),
        article_id=uuid.uuid4(),
    )


def _en_content():
    from src.modules.intelligence.domain.entities import AnalysesContent
    return AnalysesContent(
        analysis_id=uuid.uuid4(),
        language="en",
        summary="English summary",
        pain_points="English pain",
        insights="English insight",
        innovations="English innovation",
    )


def _handler(target_languages=None):
    translate_article_uc = MagicMock()
    translate_tags_uc = MagicMock()
    analyses_translation_repo = MagicMock()
    event_bus = MagicMock()
    return AnalysisCompletedHandler(
        translate_article_uc=translate_article_uc,
        translate_tags_uc=translate_tags_uc,
        analyses_translation_repo=analyses_translation_repo,
        event_bus=event_bus,
        target_languages=target_languages or ["zh-TW"],
    ), translate_article_uc, translate_tags_uc, analyses_translation_repo, event_bus


# ── Calls translate_article_uc for each target language ─────────────────────

def test_calls_translate_for_each_language():
    handler, article_uc, tags_uc, repo, bus = _handler(target_languages=["zh-TW", "ja"])
    event = _event()
    en = _en_content()
    repo.find_by_analysis_id_and_language.return_value = en
    article_uc.execute.return_value = AnalysesTranslationResult(
        analysis_id=event.analysis_id, language="zh-TW",
        content=AnalysesTranslationContent(summary="s", pain_points="p", insights="i", innovations="n"),
        success=True,
    )

    handler.handle(event)

    assert article_uc.execute.call_count == 2
    call_langs = [c.kwargs["target_language"] for c in article_uc.execute.call_args_list]
    assert call_langs == ["zh-TW", "ja"]


# ── Skips translation when English content missing ───────────────────────────

def test_skips_translation_when_no_english_content():
    handler, article_uc, tags_uc, repo, bus = _handler()
    event = _event()
    repo.find_by_analysis_id_and_language.return_value = None

    handler.handle(event)

    article_uc.execute.assert_not_called()
    bus.publish.assert_not_called()


# ── Publishes TranslationFailedEvent when article translation fails ─────────

def test_publishes_failed_event_when_translation_returns_failure():
    handler, article_uc, tags_uc, repo, bus = _handler()
    event = _event()
    en = _en_content()
    repo.find_by_analysis_id_and_language.return_value = en
    article_uc.execute.return_value = AnalysesTranslationResult(
        analysis_id=event.analysis_id, language="zh-TW",
        content=AnalysesTranslationContent(summary=None, pain_points=None, insights=None, innovations=None),
        success=False,
    )

    handler.handle(event)

    published = bus.publish.call_args[0][0]
    assert isinstance(published, TranslationFailedEvent)
    assert published.task_type == "translate_article"
    assert published.analysis_id == event.analysis_id


# ── Publishes TranslationFailedEvent when article translation throws ────────

def test_publishes_failed_event_when_translation_throws_exception():
    handler, article_uc, tags_uc, repo, bus = _handler()
    event = _event()
    en = _en_content()
    repo.find_by_analysis_id_and_language.return_value = en
    article_uc.execute.side_effect = RuntimeError("provider crashed")

    handler.handle(event)

    published = bus.publish.call_args[0][0]
    assert isinstance(published, TranslationFailedEvent)
    assert published.exception_type == "RuntimeError"
    assert "provider crashed" in published.exception_message


# ── Calls translate_tags and translate_groups for each language ─────────────

def test_calls_translate_tags_and_groups_for_each_language():
    handler, article_uc, tags_uc, repo, bus = _handler(target_languages=["zh-TW"])
    event = _event()
    en = _en_content()
    repo.find_by_analysis_id_and_language.return_value = en
    article_uc.execute.return_value = AnalysesTranslationResult(
        analysis_id=event.analysis_id, language="zh-TW",
        content=AnalysesTranslationContent(summary="s", pain_points="p", insights="i", innovations="n"),
        success=True,
    )

    handler.handle(event)

    tags_uc.translate_tags.assert_called_once_with("zh-TW", limit=50)
    tags_uc.translate_groups.assert_called_once_with("zh-TW", limit=50)


# ── Swallows tag/group translation exceptions ───────────────────────────────

def test_swallows_tag_translation_exceptions():
    handler, article_uc, tags_uc, repo, bus = _handler(target_languages=["zh-TW"])
    event = _event()
    en = _en_content()
    repo.find_by_analysis_id_and_language.return_value = en
    article_uc.execute.return_value = AnalysesTranslationResult(
        analysis_id=event.analysis_id, language="zh-TW",
        content=AnalysesTranslationContent(summary="s", pain_points="p", insights="i", innovations="n"),
        success=True,
    )
    tags_uc.translate_tags.side_effect = RuntimeError("tag LLM failed")
    tags_uc.translate_groups.return_value = {"total": 0, "success": 0, "failed": 0}

    # Should not raise
    handler.handle(event)

    tags_uc.translate_groups.assert_called_once()


def test_swallows_group_translation_exceptions():
    handler, article_uc, tags_uc, repo, bus = _handler(target_languages=["zh-TW"])
    event = _event()
    en = _en_content()
    repo.find_by_analysis_id_and_language.return_value = en
    article_uc.execute.return_value = AnalysesTranslationResult(
        analysis_id=event.analysis_id, language="zh-TW",
        content=AnalysesTranslationContent(summary="s", pain_points="p", insights="i", innovations="n"),
        success=True,
    )
    tags_uc.translate_tags.return_value = {"total": 0, "success": 0, "failed": 0}
    tags_uc.translate_groups.side_effect = RuntimeError("group LLM failed")

    # Should not raise
    handler.handle(event)

    tags_uc.translate_tags.assert_called_once()


# ── Span attribute tests ──────────────────────────────────────────────────────

def test_span_records_analysis_and_article_ids():
    handler, article_uc, tags_uc, repo, bus = _handler()
    event = _event()
    repo.find_by_analysis_id_and_language.return_value = None  # skip translation
    mock_span = MagicMock()

    with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
        handler.handle(event)

    mock_span.set_attribute.assert_any_call("analysis.id", str(event.analysis_id))
    mock_span.set_attribute.assert_any_call("article.id", str(event.article_id))


def test_span_records_target_languages():
    handler, article_uc, tags_uc, repo, bus = _handler(target_languages=["zh-TW", "ja"])
    event = _event()
    repo.find_by_analysis_id_and_language.return_value = None
    mock_span = MagicMock()

    with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
        handler.handle(event)

    mock_span.set_attribute.assert_any_call("translation.target_languages", "zh-TW, ja")
