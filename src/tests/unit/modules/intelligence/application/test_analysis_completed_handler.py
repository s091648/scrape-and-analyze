"""
Unit tests for AnalysisCompletedHandler — covers auto-translation after
tag normalization, English content prerequisite, failure event publishing,
article body translation, and tag/group translation error swallowing.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.modules.intelligence.application.event_handlers.analysis_completed_handler import (
    AnalysisCompletedHandler,
)
from src.modules.intelligence.application.events import (
    TagNormalizationCompletedEvent,
    TranslationFailedEvent,
)
from src.modules.intelligence.domain.value_objects import AnalysesTranslationResult, AnalysesTranslationContent
from src.modules.intelligence.domain.value_objects.analyses_translation_content import (
    ArticleBodyTranslationContent,
    ArticleBodyTranslationResult,
)


def _event(article_title="Test Title", article_content="Test content body."):
    return TagNormalizationCompletedEvent(
        analysis_id=uuid.uuid4(),
        article_id=uuid.uuid4(),
        article_title=article_title,
        article_content=article_content,
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


def _analysis_success(event, lang="zh-TW"):
    return AnalysesTranslationResult(
        analysis_id=event.analysis_id, language=lang,
        content=AnalysesTranslationContent(summary="s", pain_points="p", insights="i", innovations="n"),
        success=True,
    )


def _body_success(event, lang="zh-TW"):
    return ArticleBodyTranslationResult(
        article_id=event.article_id, language=lang,
        content=ArticleBodyTranslationContent(title="已翻譯標題", content="已翻譯內容"),
        success=True,
    )


def _body_failure(event, lang="zh-TW"):
    return ArticleBodyTranslationResult(
        article_id=event.article_id, language=lang,
        content=ArticleBodyTranslationContent(title=None, content=None),
        success=False,
    )


def _handler(target_languages=None):
    translate_article_uc = AsyncMock()
    translate_tags_uc = AsyncMock()
    translate_body_uc = AsyncMock()
    analyses_translation_repo = AsyncMock()
    event_bus = AsyncMock()
    handler = AnalysisCompletedHandler(
        translate_article_uc=translate_article_uc,
        translate_tags_uc=translate_tags_uc,
        translate_body_uc=translate_body_uc,
        analyses_translation_repo=analyses_translation_repo,
        event_bus=event_bus,
        target_languages=target_languages or ["zh-TW"],
    )
    return handler, translate_article_uc, translate_tags_uc, translate_body_uc, analyses_translation_repo, event_bus


# ── Calls translate_article_uc for each target language ─────────────────────

@pytest.mark.asyncio
async def test_calls_translate_for_each_language():
    handler, article_uc, tags_uc, body_uc, repo, bus = _handler(target_languages=["zh-TW", "ja"])
    event = _event()
    en = _en_content()
    repo.find_by_analysis_id_and_language.return_value = en
    article_uc.execute.return_value = _analysis_success(event)
    body_uc.execute.return_value = _body_success(event)

    await handler.handle(event)

    assert article_uc.execute.call_count == 2
    call_langs = [c.kwargs["target_language"] for c in article_uc.execute.call_args_list]
    assert call_langs == ["zh-TW", "ja"]


# ── Skips analysis translation when English content missing, but body still runs

@pytest.mark.asyncio
async def test_skips_analysis_translation_when_no_english_content_but_body_still_runs():
    handler, article_uc, tags_uc, body_uc, repo, bus = _handler()
    event = _event()
    repo.find_by_analysis_id_and_language.return_value = None
    body_uc.execute.return_value = _body_success(event)

    await handler.handle(event)

    article_uc.execute.assert_not_called()
    body_uc.execute.assert_called_once_with(
        article_id=event.article_id,
        title=event.article_title,
        content=event.article_content,
        target_language="zh-TW",
    )


# ── Publishes TranslationFailedEvent when article translation fails ─────────

@pytest.mark.asyncio
async def test_publishes_failed_event_when_translation_returns_failure():
    handler, article_uc, tags_uc, body_uc, repo, bus = _handler()
    event = _event()
    en = _en_content()
    repo.find_by_analysis_id_and_language.return_value = en
    article_uc.execute.return_value = AnalysesTranslationResult(
        analysis_id=event.analysis_id, language="zh-TW",
        content=AnalysesTranslationContent(summary=None, pain_points=None, insights=None, innovations=None),
        success=False,
    )
    body_uc.execute.return_value = _body_success(event)

    await handler.handle(event)

    published_events = [c[0][0] for c in bus.publish.call_args_list]
    failed_events = [e for e in published_events if isinstance(e, TranslationFailedEvent)]
    assert any(e.task_type == "translate_article" for e in failed_events)
    assert any(e.analysis_id == event.analysis_id for e in failed_events)


# ── Publishes TranslationFailedEvent when article translation throws ────────

@pytest.mark.asyncio
async def test_publishes_failed_event_when_translation_throws_exception():
    handler, article_uc, tags_uc, body_uc, repo, bus = _handler()
    event = _event()
    en = _en_content()
    repo.find_by_analysis_id_and_language.return_value = en
    article_uc.execute.side_effect = RuntimeError("provider crashed")
    body_uc.execute.return_value = _body_success(event)

    await handler.handle(event)

    published_events = [c[0][0] for c in bus.publish.call_args_list]
    failed_events = [e for e in published_events if isinstance(e, TranslationFailedEvent)]
    assert any(e.exception_type == "RuntimeError" for e in failed_events)
    assert any("provider crashed" in e.exception_message for e in failed_events)


# ── Calls translate_tags and translate_groups for each language ─────────────

@pytest.mark.asyncio
async def test_calls_translate_tags_and_groups_for_each_language():
    handler, article_uc, tags_uc, body_uc, repo, bus = _handler(target_languages=["zh-TW"])
    event = _event()
    en = _en_content()
    repo.find_by_analysis_id_and_language.return_value = en
    article_uc.execute.return_value = _analysis_success(event)
    body_uc.execute.return_value = _body_success(event)

    await handler.handle(event)

    tags_uc.translate_tags.assert_called_once_with("zh-TW", limit=50)
    tags_uc.translate_groups.assert_called_once_with("zh-TW", limit=50)


# ── Swallows tag/group translation exceptions ───────────────────────────────

@pytest.mark.asyncio
async def test_swallows_tag_translation_exceptions():
    handler, article_uc, tags_uc, body_uc, repo, bus = _handler(target_languages=["zh-TW"])
    event = _event()
    en = _en_content()
    repo.find_by_analysis_id_and_language.return_value = en
    article_uc.execute.return_value = _analysis_success(event)
    body_uc.execute.return_value = _body_success(event)
    tags_uc.translate_tags.side_effect = RuntimeError("tag LLM failed")
    tags_uc.translate_groups.return_value = {"total": 0, "success": 0, "failed": 0}

    await handler.handle(event)  # Should not raise

    tags_uc.translate_groups.assert_called_once()


@pytest.mark.asyncio
async def test_swallows_group_translation_exceptions():
    handler, article_uc, tags_uc, body_uc, repo, bus = _handler(target_languages=["zh-TW"])
    event = _event()
    en = _en_content()
    repo.find_by_analysis_id_and_language.return_value = en
    article_uc.execute.return_value = _analysis_success(event)
    body_uc.execute.return_value = _body_success(event)
    tags_uc.translate_tags.return_value = {"total": 0, "success": 0, "failed": 0}
    tags_uc.translate_groups.side_effect = RuntimeError("group LLM failed")

    await handler.handle(event)  # Should not raise

    tags_uc.translate_tags.assert_called_once()


# ── T035: translate_body_uc called per language ──────────────────────────────

@pytest.mark.asyncio
async def test_calls_translate_body_for_each_language():
    handler, article_uc, tags_uc, body_uc, repo, bus = _handler(target_languages=["zh-TW", "ja"])
    event = _event(article_title="My Title", article_content="My Content")
    en = _en_content()
    repo.find_by_analysis_id_and_language.return_value = en
    article_uc.execute.return_value = _analysis_success(event)
    body_uc.execute.return_value = _body_success(event)

    await handler.handle(event)

    assert body_uc.execute.call_count == 2
    call_langs = [c.kwargs["target_language"] for c in body_uc.execute.call_args_list]
    assert call_langs == ["zh-TW", "ja"]
    for c in body_uc.execute.call_args_list:
        assert c.kwargs["article_id"] == event.article_id
        assert c.kwargs["title"] == "My Title"
        assert c.kwargs["content"] == "My Content"


# ── T036: missing English content — body translation still runs ──────────────

@pytest.mark.asyncio
async def test_missing_english_content_still_calls_body_translation():
    handler, article_uc, tags_uc, body_uc, repo, bus = _handler()
    event = _event()
    repo.find_by_analysis_id_and_language.return_value = None
    body_uc.execute.return_value = _body_success(event)

    await handler.handle(event)

    article_uc.execute.assert_not_called()
    body_uc.execute.assert_called_once()


# ── T037: TranslationFailedEvent with task_type="translate_article" ──────────

@pytest.mark.asyncio
async def test_publishes_translate_article_failed_event_with_correct_task_type():
    handler, article_uc, tags_uc, body_uc, repo, bus = _handler()
    event = _event()
    en = _en_content()
    repo.find_by_analysis_id_and_language.return_value = en
    article_uc.execute.return_value = AnalysesTranslationResult(
        analysis_id=event.analysis_id, language="zh-TW",
        content=AnalysesTranslationContent(summary=None, pain_points=None, insights=None, innovations=None),
        success=False,
    )
    body_uc.execute.return_value = _body_success(event)

    await handler.handle(event)

    published_events = [c[0][0] for c in bus.publish.call_args_list]
    failed = [e for e in published_events if isinstance(e, TranslationFailedEvent)]
    assert any(e.task_type == "translate_article" for e in failed)


# ── T038: TranslationFailedEvent with task_type="translate_article_body" ─────

@pytest.mark.asyncio
async def test_publishes_translate_article_body_failed_event_with_correct_task_type():
    handler, article_uc, tags_uc, body_uc, repo, bus = _handler()
    event = _event()
    en = _en_content()
    repo.find_by_analysis_id_and_language.return_value = en
    article_uc.execute.return_value = _analysis_success(event)
    body_uc.execute.return_value = _body_failure(event)

    await handler.handle(event)

    published_events = [c[0][0] for c in bus.publish.call_args_list]
    failed = [e for e in published_events if isinstance(e, TranslationFailedEvent)]
    assert any(e.task_type == "translate_article_body" for e in failed)
    assert any(e.article_id == event.article_id for e in failed)


# ── Span attribute tests ──────────────────────────────────────────────────────

def _mock_tracer(mock_span):
    """024-async-pipeline-refactor: AnalysisCompletedHandler now owns its own
    module-level _tracer and creates a fresh span via
    _tracer.start_as_current_span(...) rather than attaching attributes to an
    ambient span, so tests mock the module's _tracer instead of
    opentelemetry.trace.get_current_span. The outer span and the per-language
    lang_span both resolve to the same mocked context manager here, which is
    fine since these tests only assert attributes were set somewhere, not on
    which specific span."""
    tracer = MagicMock()
    tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
    tracer.start_as_current_span.return_value.__exit__.return_value = False
    return tracer


@pytest.mark.asyncio
async def test_span_records_analysis_and_article_ids():
    handler, article_uc, tags_uc, body_uc, repo, bus = _handler()
    event = _event()
    repo.find_by_analysis_id_and_language.return_value = None
    body_uc.execute.return_value = _body_success(event)
    mock_span = MagicMock()

    with patch("src.modules.intelligence.application.event_handlers.analysis_completed_handler._tracer",
               _mock_tracer(mock_span)):
        await handler.handle(event)

    mock_span.set_attribute.assert_any_call("analysis.id", str(event.analysis_id))
    mock_span.set_attribute.assert_any_call("article.id", str(event.article_id))


@pytest.mark.asyncio
async def test_span_records_target_languages():
    handler, article_uc, tags_uc, body_uc, repo, bus = _handler(target_languages=["zh-TW", "ja"])
    event = _event()
    repo.find_by_analysis_id_and_language.return_value = None
    body_uc.execute.return_value = _body_success(event)
    mock_span = MagicMock()

    with patch("src.modules.intelligence.application.event_handlers.analysis_completed_handler._tracer",
               _mock_tracer(mock_span)):
        await handler.handle(event)

    mock_span.set_attribute.assert_any_call("translation.target_languages", "zh-TW, ja")
