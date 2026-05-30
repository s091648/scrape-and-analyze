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
    topic.tag_mode = 'unsupervised'
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


def test_build_prompt_uses_supervised_template_when_tag_mode_supervised(deps):
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    from src.modules.intelligence.domain.repositories import TagGroupDefinitionRepository

    topic = MagicMock()
    topic.display_name = "AI"
    topic.tag_mode = 'supervised'
    deps["topic_repository"].find_by_id.return_value = topic

    group = MagicMock()
    group.name = "research_methods"
    group.display_name = "Research Methods"
    group.description = ""
    deps["tag_group_definition_repository"].find_by_topic_id.return_value = [group]
    deps["llm_service"].analyze.return_value = _make_llm_result()

    uc = AnalyzeArticleUseCase(**deps, prompt=AnalysisPrompt())
    uc.execute(_make_article(topic_id=uuid.uuid4()))

    called_prompt = deps["llm_service"].analyze.call_args[0][1]
    assert "research_methods" in called_prompt
    assert "ONLY these exact key strings" in called_prompt


def test_build_prompt_uses_semi_supervised_template_when_tag_mode_semi(deps):
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase

    topic = MagicMock()
    topic.display_name = "AI"
    topic.tag_mode = 'semi_supervised'
    deps["topic_repository"].find_by_id.return_value = topic

    group = MagicMock()
    group.name = "applications"
    group.display_name = "Applications"
    group.description = ""
    deps["tag_group_definition_repository"].find_by_topic_id.return_value = [group]
    deps["llm_service"].analyze.return_value = _make_llm_result()

    uc = AnalyzeArticleUseCase(**deps, prompt=AnalysisPrompt())
    uc.execute(_make_article(topic_id=uuid.uuid4()))

    called_prompt = deps["llm_service"].analyze.call_args[0][1]
    assert "applications" in called_prompt
    assert "EXISTING TAG GROUPS" in called_prompt


# ── US1: ArXiv content truncation ────────────────────────────────────────────

def test_arxiv_content_truncated_to_15000_chars(deps):
    deps["llm_service"].analyze.return_value = _make_llm_result()
    uc = _make_uc(deps)
    big_sections = {"introduction": "a" * 9000, "methods": "b" * 9000}
    article = _make_article(source="arxiv", metadata={"sections": big_sections})

    uc.execute(article)

    called_content = deps["llm_service"].analyze.call_args[0][0]
    assert len(called_content) <= 15000


# ── US1: Token recording ──────────────────────────────────────────────────────

def test_analysis_metadata_recorded_on_success(deps):
    from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata
    content = AnalysisContent(tag_groups=[], pain_points="p", insights="i", innovations="n", summary="s")
    metadata = AnalysisMetadata(model_used="gemini-3-flash", input_tokens=1234, output_tokens=567)
    deps["llm_service"].analyze.return_value = (content, metadata)
    uc = _make_uc(deps)

    result = uc.execute(_make_article())

    assert result.success is True
    assert result.analysis.analysis_metadata.model_used == "gemini-3-flash"
    assert result.analysis.analysis_metadata.input_tokens == 1234
    assert result.analysis.analysis_metadata.output_tokens == 567


# ── US1: No topic_id uses all active topics ───────────────────────────────────

def test_no_topic_id_uses_all_active_topics_auto_mode(deps):
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase

    topic1 = MagicMock()
    topic1.display_name = "Machine Learning"
    topic2 = MagicMock()
    topic2.display_name = "Computer Vision"
    deps["topic_repository"].list_active.return_value = [topic1, topic2]
    deps["topic_repository"].find_by_id.return_value = None
    deps["llm_service"].analyze.return_value = _make_llm_result()

    uc = AnalyzeArticleUseCase(**deps, prompt=AnalysisPrompt())
    uc.execute(_make_article(topic_id=None))

    called_prompt = deps["llm_service"].analyze.call_args[0][1]
    assert "Machine Learning" in called_prompt
    assert "Computer Vision" in called_prompt
    assert "ONLY these exact key strings" not in called_prompt


# ── US2: Supervised fallback to auto when no tag groups ───────────────────────

def test_supervised_fallback_to_auto_when_no_tag_groups(deps):
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase

    topic = MagicMock()
    topic.display_name = "AI Research"
    topic.tag_mode = 'supervised'
    deps["topic_repository"].find_by_id.return_value = topic
    deps["tag_group_definition_repository"].find_by_topic_id.return_value = []
    deps["topic_repository"].list_active.return_value = []
    deps["llm_service"].analyze.return_value = _make_llm_result()

    uc = AnalyzeArticleUseCase(**deps, prompt=AnalysisPrompt())
    uc.execute(_make_article(topic_id=uuid.uuid4()))

    called_prompt = deps["llm_service"].analyze.call_args[0][1]
    assert "ONLY these exact key strings" not in called_prompt
    assert "AI Research" in called_prompt


# ── US2: Semi-supervised also upserts tag groups ──────────────────────────────

def test_semi_supervised_mode_also_upserts_tag_groups(deps):
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    from src.modules.intelligence.domain.value_objects import AnalysisTagGroup

    topic = MagicMock()
    topic.display_name = "AI"
    topic.tag_mode = 'semi_supervised'
    deps["topic_repository"].find_by_id.return_value = topic
    deps["topic_repository"].list_active.return_value = []

    tag_groups = [AnalysisTagGroup(group_name="new_category", tags=["tag1"])]
    content = AnalysisContent(
        tag_groups=tag_groups, pain_points="p", insights="i", innovations="n", summary="s"
    )
    metadata = AnalysisMetadata(model_used="test", input_tokens=1, output_tokens=1)
    deps["llm_service"].analyze.return_value = (content, metadata)

    uc = AnalyzeArticleUseCase(**deps, prompt=AnalysisPrompt())
    uc.execute(_make_article(topic_id=uuid.uuid4()))

    deps["tag_group_definition_repository"].upsert.assert_called()


# ── US5: Embedding failure does not block persistence ─────────────────────────

def test_embedding_failure_does_not_block_analysis_persistence(deps):
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    from src.modules.intelligence.domain.value_objects import AnalysisTagGroup

    embedding_svc = MagicMock()
    embedding_svc.embed_batch.side_effect = RuntimeError("embedding service down")

    topic = MagicMock()
    topic.display_name = "AI"
    topic.tag_mode = 'unsupervised'
    deps["topic_repository"].find_by_id.return_value = topic
    deps["topic_repository"].list_active.return_value = []

    tag_groups = [AnalysisTagGroup(group_name="methods", tags=["transformer"])]
    content = AnalysisContent(
        tag_groups=tag_groups, pain_points="p", insights="i", innovations="n", summary="s"
    )
    metadata = AnalysisMetadata(model_used="test", input_tokens=1, output_tokens=1)
    deps["llm_service"].analyze.return_value = (content, metadata)

    uc = AnalyzeArticleUseCase(**deps, embedding_service=embedding_svc, prompt=AnalysisPrompt())
    result = uc.execute(_make_article(topic_id=uuid.uuid4()))

    assert result.success is True
    deps["analysis_repository"].save.assert_called_once()


# ── T039: Unsupervised mode prompt allows free group key generation ──────────

def test_unsupervised_mode_prompt_allows_free_group_key_generation(deps):
    """In unsupervised mode, the prompt does NOT constrain LLM to predefined groups."""
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase

    topic = MagicMock()
    topic.display_name = "AI Research"
    topic.tag_mode = 'unsupervised'
    deps["topic_repository"].find_by_id.return_value = topic
    deps["topic_repository"].list_active.return_value = []
    deps["llm_service"].analyze.return_value = _make_llm_result()

    uc = AnalyzeArticleUseCase(**deps, prompt=AnalysisPrompt())
    uc.execute(_make_article(topic_id=uuid.uuid4()))

    called_prompt = deps["llm_service"].analyze.call_args[0][1]
    # Unsupervised prompt must NOT contain constraint phrases from supervised/semi
    assert "ONLY these exact key strings" not in called_prompt
    assert "EXISTING TAG GROUPS" not in called_prompt
    # Unsupervised prompt must encourage free group generation
    assert "tag groups of your choosing" in called_prompt
    assert "AI Research" in called_prompt


def test_supervised_mode_does_not_upsert_tag_groups(deps):
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata, AnalysisTagGroup

    topic = MagicMock()
    topic.display_name = "AI"
    topic.tag_mode = 'supervised'
    deps["topic_repository"].find_by_id.return_value = topic

    group = MagicMock()
    group.name = "research_methods"
    group.display_name = "Research Methods"
    group.description = ""
    deps["tag_group_definition_repository"].find_by_topic_id.return_value = [group]

    tag_groups = [AnalysisTagGroup(group_name="new_group", tags=["tag1"])]
    content = AnalysisContent(
        tag_groups=tag_groups, pain_points="p", insights="i", innovations="n", summary="s"
    )
    deps["llm_service"].analyze.return_value = (
        content,
        AnalysisMetadata(model_used="test", input_tokens=1, output_tokens=1),
    )

    uc = AnalyzeArticleUseCase(**deps, prompt=AnalysisPrompt())
    uc.execute(_make_article(topic_id=uuid.uuid4()))

    deps["tag_group_definition_repository"].upsert.assert_not_called()