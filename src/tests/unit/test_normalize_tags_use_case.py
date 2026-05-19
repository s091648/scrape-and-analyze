import uuid
from unittest.mock import MagicMock, call

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

    embed_svc.embed.return_value = [0.1] * 768
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

    embed_svc.embed.return_value = [0.1] * 768
    tag_repo.find_similar.return_value = [(existing_tag, 0.88)]  # mid range
    tag_repo.save.return_value = new_tag

    uc.execute(analysis_id=analysis_id, article_id=article_id,
               tag_groups=[("digital_twin", ["real time sync"])])

    tag_repo.save.assert_called_once_with("real time sync", "digital_twin", [0.1] * 768)
    tag_repo.link_to_article.assert_called_once_with(new_tag.id, article_id)
    tag_repo.save_suggestion.assert_called_once()
    suggestion: TagNormalizationSuggestion = tag_repo.save_suggestion.call_args[0][0]
    assert suggestion.new_tag_id == new_tag.id
    assert suggestion.existing_tag_id == existing_tag.id
    assert suggestion.similarity_score == pytest.approx(0.88)


def test_low_similarity_saves_new_tag_without_suggestion():
    uc, embed_svc, tag_repo = _make_use_case()
    new_tag = TagData(id=uuid.uuid4(), name="brand new concept", tag_group_name="digital_twin")

    embed_svc.embed.return_value = [0.1] * 768
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

    embed_svc.embed.assert_not_called()
    tag_repo.save.assert_not_called()


def test_execute_returns_success_result():
    from src.modules.intelligence.application.use_cases.normalize_tags import NormalizeTagsResult
    uc, embed_svc, tag_repo = _make_use_case()
    a_id = uuid.uuid4()
    tag_repo.find_similar.return_value = []
    tag_repo.save.return_value = TagData(id=uuid.uuid4(), name="t", tag_group_name="g")

    result = uc.execute(analysis_id=a_id, article_id=uuid.uuid4(),
                        tag_groups=[("g", ["t"])])

    assert result.success is True
    assert result.analysis_id == a_id
