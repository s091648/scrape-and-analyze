"""
Unit tests for AnalyzeArticleUseCase — covers success path, LLM failure,
and save failure, verifying AnalysisResult is returned correctly.
"""
import uuid
from unittest.mock import MagicMock, call

import pytest

from src.shared.domain.entities import Article
from src.modules.intelligence.application.use_cases import AnalysisResult
from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata, AnalysisPrompt


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
        "tag_group_definition_repository": MagicMock(),
    }


def _make_uc(deps, embedding_service=None):
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    deps["topic_repository"].find_by_id.return_value = None
    deps["topic_repository"].list_active.return_value = []
    return AnalyzeArticleUseCase(**deps, embedding_service=embedding_service, prompt=AnalysisPrompt())


# ── success path ────────────────────────────────────────────────────────────

def test_execute_success_saves_analysis_and_returns_result(deps):
    deps["llm_service"].analyze.return_value = _make_llm_result()
    uc = _make_uc(deps)

    result = uc.execute(_make_article())

    assert result.success is True
    assert result.analysis is not None
    deps["analysis_repository"].save.assert_called_once()


# ── LLM failure ─────────────────────────────────────────────────────────────

def test_execute_returns_failure_result_when_llm_returns_none(deps):
    deps["llm_service"].analyze.return_value = None
    uc = _make_uc(deps)
    article = _make_article()

    result = uc.execute(article)

    assert result.success is False
    assert result.article_id == article.id
    assert result.article_url == article.url
    assert result.exception_type == "LLMAnalysisError"
    deps["analysis_repository"].save.assert_not_called()


# ── save failure ─────────────────────────────────────────────────────────────

def test_execute_returns_failure_result_when_save_raises(deps):
    deps["llm_service"].analyze.return_value = _make_llm_result()
    deps["analysis_repository"].save.side_effect = RuntimeError("DB down")
    uc = _make_uc(deps)
    article = _make_article()

    result = uc.execute(article)

    assert result.success is False
    assert result.exception_type == "RuntimeError"
    assert "DB down" in result.exception_message


# ── AnalysisResult dataclass ────────────────────────────────────────────

def test_analysis_result_is_frozen():
    article_id = uuid.uuid4()
    result = AnalysisResult(
        success=False,
        article_id=article_id,
        article_url="https://x.com",
        exception_type="SomeError",
        exception_message="details",
    )
    assert result.article_id == article_id
    with pytest.raises((TypeError, AttributeError)):
        result.success = True  # type: ignore[misc]


def test_analysis_result_optional_fields_default_to_none():
    result = AnalysisResult(
        success=False,
        article_id=uuid.uuid4(),
        article_url="https://x.com",
    )
    assert result.analysis is None
    assert result.exception_type is None
    assert result.exception_message is None


def test_upsert_generates_embedding_for_new_tag_groups(deps):
    """In auto mode, _upsert_generated_tag_groups calls embedding_service.embed_batch."""
    from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata, AnalysisTagGroup
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase

    embedding_svc = MagicMock()
    embedding_svc.embed_batch.return_value = [[0.1] * 768, [0.2] * 768]

    topic = MagicMock()
    topic.display_name = "AI"
    topic.auto_tag_groups = True
    deps["topic_repository"].find_by_id.return_value = topic
    deps["topic_repository"].list_active.return_value = []

    tag_groups = [
        AnalysisTagGroup(group_name="research_methods", tags=["transformer"]),
        AnalysisTagGroup(group_name="applications", tags=["cv"]),
    ]
    content = AnalysisContent(
        tag_groups=tag_groups, pain_points="p", insights="i", innovations="n", summary="s"
    )
    metadata = AnalysisMetadata(model_used="test", input_tokens=1, output_tokens=1)
    deps["llm_service"].analyze.return_value = (content, metadata)

    uc = AnalyzeArticleUseCase(
        **deps,
        embedding_service=embedding_svc,
        prompt=AnalysisPrompt(),
    )
    article = _make_article(topic_id=uuid.uuid4())
    uc.execute(article)

    embedding_svc.embed_batch.assert_called_once()
    called_texts = embedding_svc.embed_batch.call_args[0][0]
    assert any("research_methods" in t for t in called_texts)
    assert any("applications" in t for t in called_texts)