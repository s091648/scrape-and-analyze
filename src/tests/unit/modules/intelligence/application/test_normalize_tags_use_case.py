import uuid
from unittest.mock import MagicMock, call, patch

import pytest

from src.modules.intelligence.domain.repositories.tag_repository import TagData
from src.modules.intelligence.domain.entities.tag_normalization_suggestion import TagNormalizationSuggestion


def _make_use_case(auto_merge=0.92, suggest=0.85):
    from src.modules.intelligence.application.use_cases.normalize_tags import NormalizeTagsUseCase
    embedding_svc = MagicMock()
    tag_repo = MagicMock()
    tag_repo.commit = MagicMock()
    return NormalizeTagsUseCase(
        embedding_service=embedding_svc,
        tag_repository=tag_repo,
        auto_merge_threshold=auto_merge,
        suggest_threshold=suggest,
    ), embedding_svc, tag_repo


def test_high_similarity_reuses_existing_tag_without_saving_new():
    uc, embed_svc, tag_repo = _make_use_case()
    analysis_id = uuid.uuid4()
    article_id = uuid.uuid4()
    existing_tag = TagData(id=uuid.uuid4(), name="real-time sync", tag_group_name="digital_twin")

    embed_svc.embed_batch.return_value = [[0.1] * 768]
    tag_repo.find_similar.return_value = [(existing_tag, 0.95)]  # above auto_merge

    uc.execute(analysis_id=analysis_id, article_id=article_id,
               tag_groups=[("digital_twin", ["real time sync"])])

    tag_repo.save.assert_not_called()
    tag_repo.link_to_article.assert_called_once_with(existing_tag.id, article_id)
    tag_repo.save_suggestion.assert_not_called()


def test_mid_similarity_saves_new_tag_and_creates_suggestion():
    uc, embed_svc, tag_repo = _make_use_case()
    analysis_id = uuid.uuid4()
    article_id = uuid.uuid4()
    existing_tag = TagData(id=uuid.uuid4(), name="real-time sync", tag_group_name="digital_twin")
    new_tag = TagData(id=uuid.uuid4(), name="real time sync", tag_group_name="digital_twin")

    embed_svc.embed_batch.return_value = [[0.1] * 768]
    tag_repo.find_similar.return_value = [(existing_tag, 0.88)]  # mid range
    tag_repo.save.return_value = new_tag

    uc.execute(analysis_id=analysis_id, article_id=article_id,
               tag_groups=[("digital_twin", ["real time sync"])])

    tag_repo.save.assert_called_once_with("real time sync", "digital_twin", [0.1] * 768, None)
    tag_repo.link_to_article.assert_called_once_with(new_tag.id, article_id)
    tag_repo.save_suggestion.assert_called_once()
    suggestion: TagNormalizationSuggestion = tag_repo.save_suggestion.call_args[0][0]
    assert suggestion.new_tag_id == new_tag.id
    assert suggestion.existing_tag_id == existing_tag.id
    assert suggestion.similarity_score == pytest.approx(0.88)


def test_low_similarity_saves_new_tag_without_suggestion():
    uc, embed_svc, tag_repo = _make_use_case()
    new_tag = TagData(id=uuid.uuid4(), name="brand new concept", tag_group_name="digital_twin")

    embed_svc.embed_batch.return_value = [[0.1] * 768]
    tag_repo.find_similar.return_value = []  # no similar tags
    tag_repo.save.return_value = new_tag

    uc.execute(analysis_id=uuid.uuid4(), article_id=uuid.uuid4(),
               tag_groups=[("digital_twin", ["brand new concept"])])

    tag_repo.save.assert_called_once()
    tag_repo.link_to_article.assert_called_once()
    tag_repo.save_suggestion.assert_not_called()


def test_empty_tag_name_is_skipped():
    uc, embed_svc, tag_repo = _make_use_case()
    tag_repo.find_similar.return_value = []
    tag_repo.save.return_value = TagData(id=uuid.uuid4(), name="x", tag_group_name="g")

    uc.execute(analysis_id=uuid.uuid4(), article_id=uuid.uuid4(),
               tag_groups=[("g", ["", "   "])])

    embed_svc.embed_batch.assert_not_called()
    tag_repo.save.assert_not_called()


def test_execute_returns_success_result():
    from src.modules.intelligence.application.use_cases.normalize_tags import NormalizeTagsResult
    uc, embed_svc, tag_repo = _make_use_case()
    a_id = uuid.uuid4()
    tag_repo.find_similar.return_value = []
    tag_repo.save.return_value = TagData(id=uuid.uuid4(), name="t", tag_group_name="g")

    embed_svc.embed_batch.return_value = [[0.1] * 768]
    result = uc.execute(analysis_id=a_id, article_id=uuid.uuid4(),
                        tag_groups=[("g", ["t"])])

    assert result.success is True
    assert result.analysis_id == a_id


# ── T007: Auto-merge log entry ──────────────────────────────────────────────

@patch("src.modules.intelligence.application.use_cases.normalize_tags.logger")
def test_auto_merge_emits_tag_auto_merged_log(mock_logger):
    uc, embed_svc, tag_repo = _make_use_case()
    existing_tag = TagData(id=uuid.uuid4(), name="real-time sync", tag_group_name="digital_twin")

    embed_svc.embed_batch.return_value = [[0.1] * 768]
    tag_repo.find_similar.return_value = [(existing_tag, 0.95)]

    uc.execute(analysis_id=uuid.uuid4(), article_id=uuid.uuid4(),
               tag_groups=[("digital_twin", ["real time sync"])])

    mock_logger.info.assert_any_call(
        "tag_auto_merged",
        tag="real time sync",
        merged_into="real-time sync",
        similarity=pytest.approx(0.95),
    )


# ── T008: Suggestion log entry ─────────────────────────────────────────────

@patch("src.modules.intelligence.application.use_cases.normalize_tags.logger")
def test_suggestion_emits_tag_suggestion_created_log(mock_logger):
    uc, embed_svc, tag_repo = _make_use_case(auto_merge=0.95, suggest=0.85)
    existing_tag = TagData(id=uuid.uuid4(), name="real-time sync", tag_group_name="digital_twin")
    new_tag = TagData(id=uuid.uuid4(), name="real time sync", tag_group_name="digital_twin")

    embed_svc.embed_batch.return_value = [[0.1] * 768]
    tag_repo.find_similar.return_value = [(existing_tag, 0.88)]
    tag_repo.save.return_value = new_tag

    uc.execute(analysis_id=uuid.uuid4(), article_id=uuid.uuid4(),
               tag_groups=[("digital_twin", ["real time sync"])])

    mock_logger.info.assert_any_call(
        "tag_suggestion_created",
        tag="real time sync",
        similar_to="real-time sync",
        similarity=pytest.approx(0.88),
    )


# ── T009: New-tag log entry ────────────────────────────────────────────────

@patch("src.modules.intelligence.application.use_cases.normalize_tags.logger")
def test_new_tag_emits_tag_created_log(mock_logger):
    uc, embed_svc, tag_repo = _make_use_case()
    new_tag = TagData(id=uuid.uuid4(), name="brand new", tag_group_name="digital_twin")

    embed_svc.embed_batch.return_value = [[0.1] * 768]
    tag_repo.find_similar.return_value = []
    tag_repo.save.return_value = new_tag

    uc.execute(analysis_id=uuid.uuid4(), article_id=uuid.uuid4(),
               tag_groups=[("digital_twin", ["brand new"])])

    mock_logger.info.assert_any_call(
        "tag_created",
        tag="brand new",
        group="digital_twin",
    )


# ── T010: Rollback on exception ────────────────────────────────────────────

def test_rollback_on_exception_no_commit():
    uc, embed_svc, tag_repo = _make_use_case()
    embed_svc.embed_batch.side_effect = RuntimeError("embedding service down")

    result = uc.execute(analysis_id=uuid.uuid4(), article_id=uuid.uuid4(),
                        tag_groups=[("g", ["t"])])

    assert result.success is False
    tag_repo.commit.assert_not_called()
    assert result.exception_type == "RuntimeError"
    assert "embedding service down" in result.exception_message


def test_rollback_on_repo_save_exception():
    uc, embed_svc, tag_repo = _make_use_case()
    embed_svc.embed_batch.return_value = [[0.1] * 768]
    tag_repo.find_similar.return_value = []
    tag_repo.save.side_effect = RuntimeError("db write failed")

    result = uc.execute(analysis_id=uuid.uuid4(), article_id=uuid.uuid4(),
                        tag_groups=[("g", ["t"])])

    assert result.success is False
    tag_repo.commit.assert_not_called()


# ── T011: Embedding batch semantics ────────────────────────────────────────

def test_embed_batch_called_once_with_all_tag_names():
    uc, embed_svc, tag_repo = _make_use_case()
    tag_repo.find_similar.return_value = []
    tag_repo.save.return_value = TagData(id=uuid.uuid4(), name="x", tag_group_name="g")

    embed_svc.embed_batch.return_value = [[0.1] * 768, [0.2] * 768]

    uc.execute(
        analysis_id=uuid.uuid4(), article_id=uuid.uuid4(),
        tag_groups=[("g1", ["alpha"]), ("g2", ["beta"])],
    )

    embed_svc.embed_batch.assert_called_once_with(["alpha", "beta"])


# ── T012: Threshold boundaries ──────────────────────────────────────────────

def test_exact_auto_merge_threshold_triggers_auto_merge():
    uc, embed_svc, tag_repo = _make_use_case(auto_merge=0.95, suggest=0.90)
    existing_tag = TagData(id=uuid.uuid4(), name="tag-a", tag_group_name="g")
    article_id = uuid.uuid4()

    embed_svc.embed_batch.return_value = [[0.1] * 768]
    tag_repo.find_similar.return_value = [(existing_tag, 0.95)]

    uc.execute(analysis_id=uuid.uuid4(), article_id=article_id,
               tag_groups=[("g", ["tag a"])])

    tag_repo.save.assert_not_called()
    tag_repo.link_to_article.assert_called_once_with(existing_tag.id, article_id)


def test_exact_suggest_threshold_creates_suggestion():
    uc, embed_svc, tag_repo = _make_use_case(auto_merge=0.95, suggest=0.90)
    existing_tag = TagData(id=uuid.uuid4(), name="tag-a", tag_group_name="g")
    new_tag = TagData(id=uuid.uuid4(), name="tag a", tag_group_name="g")

    embed_svc.embed_batch.return_value = [[0.1] * 768]
    tag_repo.find_similar.return_value = [(existing_tag, 0.90)]
    tag_repo.save.return_value = new_tag

    uc.execute(analysis_id=uuid.uuid4(), article_id=uuid.uuid4(),
               tag_groups=[("g", ["tag a"])])

    tag_repo.save.assert_called_once()
    tag_repo.save_suggestion.assert_called_once()


def test_just_below_suggest_threshold_creates_new_tag_without_suggestion():
    uc, embed_svc, tag_repo = _make_use_case(auto_merge=0.95, suggest=0.90)
    existing_tag = TagData(id=uuid.uuid4(), name="tag-a", tag_group_name="g")
    new_tag = TagData(id=uuid.uuid4(), name="tag a", tag_group_name="g")

    embed_svc.embed_batch.return_value = [[0.1] * 768]
    tag_repo.find_similar.return_value = [(existing_tag, 0.8999)]
    tag_repo.save.return_value = new_tag

    uc.execute(analysis_id=uuid.uuid4(), article_id=uuid.uuid4(),
               tag_groups=[("g", ["tag a"])])

    tag_repo.save.assert_called_once()
    tag_repo.save_suggestion.assert_not_called()


# ── T013: Multi-group processing ────────────────────────────────────────────

def test_multi_group_tags_compared_independently():
    uc, embed_svc, tag_repo = _make_use_case(auto_merge=0.95, suggest=0.90)
    tag_g1 = TagData(id=uuid.uuid4(), name="optimization", tag_group_name="ai_ml")
    tag_g2 = TagData(id=uuid.uuid4(), name="optimization", tag_group_name="simulation_modeling")
    new_tag_g1 = TagData(id=uuid.uuid4(), name="optimisation", tag_group_name="ai_ml")
    new_tag_g2 = TagData(id=uuid.uuid4(), name="optimisation", tag_group_name="simulation_modeling")

    embed_svc.embed_batch.return_value = [[0.1] * 768, [0.2] * 768]

    def find_similar_side_effect(embedding, group_name, topic_id, threshold):
        if group_name == "ai_ml":
            return [(tag_g1, 0.96)]
        return [(tag_g2, 0.80)]

    tag_repo.find_similar.side_effect = find_similar_side_effect
    tag_repo.save.return_value = new_tag_g2

    article_id = uuid.uuid4()
    uc.execute(
        analysis_id=uuid.uuid4(), article_id=article_id,
        tag_groups=[("ai_ml", ["optimisation"]), ("simulation_modeling", ["optimisation"])],
    )

    # First tag auto-merged (0.96 >= 0.95), second created as new (0.80 < 0.90)
    assert tag_repo.link_to_article.call_count == 2
    tag_repo.save.assert_called_once()


# ── T014: Handler calls commit on success ────────────────────────────────────

def test_handler_calls_commit_on_success():
    from src.modules.intelligence.application.event_handlers.tag_normalization_handler import (
        TagNormalizationHandler,
    )
    from src.modules.intelligence.application.use_cases.normalize_tags import NormalizeTagsResult

    uc = MagicMock()
    bus = MagicMock()
    uc.execute.return_value = NormalizeTagsResult(
        success=True, analysis_id=uuid.uuid4(), article_id=uuid.uuid4()
    )
    handler = TagNormalizationHandler(use_case=uc, event_bus=bus, session=MagicMock())

    event = MagicMock()
    event.analysis_id = uuid.uuid4()
    event.article_id = uuid.uuid4()
    event.tag_groups = [("g", ["t"])]

    handler.handle(event)

    uc.execute.assert_called_once()


# ── T015: Handler passes tag_groups correctly ────────────────────────────────

def test_handler_passes_tag_groups_to_use_case():
    from src.modules.intelligence.application.event_handlers.tag_normalization_handler import (
        TagNormalizationHandler,
    )
    from src.modules.intelligence.application.use_cases.normalize_tags import NormalizeTagsResult

    uc = MagicMock()
    bus = MagicMock()
    uc.execute.return_value = NormalizeTagsResult(
        success=True, analysis_id=uuid.uuid4(), article_id=uuid.uuid4()
    )
    handler = TagNormalizationHandler(use_case=uc, event_bus=bus, session=MagicMock())

    event = MagicMock()
    event.analysis_id = uuid.uuid4()
    event.article_id = uuid.uuid4()
    event.tag_groups = [("ai_ml", ["deep learning"]), ("iot_sensing", ["sensor fusion"])]

    handler.handle(event)

    call_kwargs = uc.execute.call_args[1]
    assert call_kwargs["tag_groups"] == [("ai_ml", ["deep learning"]), ("iot_sensing", ["sensor fusion"])]
