"""
Unit tests for AnalyzeArticleUseCase — covers success path, LLM failure,
and save failure, verifying AnalysisFailedEvent is published correctly.
"""
import uuid
from unittest.mock import MagicMock, call

import pytest

from src.shared.domain.entities import Article
from src.modules.intelligence.application.events import AnalysisFailedEvent
from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata


def _make_article(**kwargs):
    defaults = dict(
        url="https://example.com/a",
        url_hash="a" * 64,
        source="rss",
        title="Title",
        content="Body text.",
    )
    defaults.update(kwargs)
    return Article(**defaults)


def _make_llm_result():
    content = AnalysisContent(
        tag_groups=[], pain_points="p", insights="i", innovations="n", summary="s"
    )
    metadata = AnalysisMetadata(model_used="test-model", input_tokens=10, output_tokens=5)
    return (content, metadata)


@pytest.fixture
def deps():
    """Return a dict of mocked collaborators for AnalyzeArticleUseCase."""
    return {
        "llm_service": MagicMock(),
        "analysis_repository": MagicMock(),
        "topic_repository": MagicMock(),
        "event_bus": MagicMock(),
    }


def _make_uc(deps):
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    deps["topic_repository"].find_by_id.return_value = None
    deps["topic_repository"].list_active.return_value = []
    return AnalyzeArticleUseCase(**deps)


# ── success path ────────────────────────────────────────────────────────────

def test_execute_success_saves_analysis_and_returns_true(deps):
    deps["llm_service"].analyze.return_value = _make_llm_result()
    uc = _make_uc(deps)

    result = uc.execute(_make_article())

    assert result is True
    deps["analysis_repository"].save.assert_called_once()
    deps["event_bus"].publish.assert_not_called()


# ── LLM failure ─────────────────────────────────────────────────────────────

def test_execute_publishes_analysis_failed_event_when_llm_returns_none(deps):
    deps["llm_service"].analyze.return_value = None
    uc = _make_uc(deps)
    article = _make_article()

    result = uc.execute(article)

    assert result is False
    deps["analysis_repository"].save.assert_not_called()

    deps["event_bus"].publish.assert_called_once()
    event = deps["event_bus"].publish.call_args[0][0]
    assert isinstance(event, AnalysisFailedEvent)
    assert event.article_id == article.id
    assert event.article_url == article.url
    assert event.exception_type == "LLMAnalysisError"


# ── save failure ─────────────────────────────────────────────────────────────

def test_execute_publishes_analysis_failed_event_when_save_raises(deps):
    deps["llm_service"].analyze.return_value = _make_llm_result()
    deps["analysis_repository"].save.side_effect = RuntimeError("DB down")
    uc = _make_uc(deps)
    article = _make_article()

    result = uc.execute(article)

    assert result is False
    deps["event_bus"].publish.assert_called_once()
    event = deps["event_bus"].publish.call_args[0][0]
    assert isinstance(event, AnalysisFailedEvent)
    assert event.exception_type == "RuntimeError"
    assert "DB down" in event.exception_message


# ── no event_bus ────────────────────────────────────────────────────────────

def test_execute_without_event_bus_still_returns_false_on_llm_failure(deps):
    deps["event_bus"] = None
    deps["llm_service"].analyze.return_value = None
    uc = _make_uc(deps)

    result = uc.execute(_make_article())

    assert result is False  # no AttributeError raised


# ── AnalysisFailedEvent dataclass ────────────────────────────────────────────

def test_analysis_failed_event_is_frozen():
    article_id = uuid.uuid4()
    event = AnalysisFailedEvent(
        article_id=article_id,
        article_url="https://x.com",
        exception_type="SomeError",
        exception_message="details",
    )
    assert event.article_id == article_id
    with pytest.raises((TypeError, AttributeError)):
        event.article_id = uuid.uuid4()  # type: ignore[misc]


def test_analysis_failed_event_optional_fields_default_to_none():
    event = AnalysisFailedEvent(article_id=uuid.uuid4(), article_url="https://x.com")
    assert event.exception_type is None
    assert event.exception_message is None
