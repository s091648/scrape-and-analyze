import uuid
import pytest

from src.modules.intelligence.domain.entities.tag_normalization_suggestion import TagNormalizationSuggestion
from src.modules.intelligence.domain.exceptions import (
    InvalidSuggestionStatusError,
    InvalidSimilarityScoreError,
)


def _make_suggestion(**overrides):
    kwargs = dict(
        new_tag_id=uuid.uuid4(),
        existing_tag_id=uuid.uuid4(),
        similarity_score=0.85,
        article_id=uuid.uuid4(),
    )
    kwargs.update(overrides)
    return TagNormalizationSuggestion(**kwargs)


@pytest.mark.parametrize("status", ["pending", "approved", "rejected"])
def test_valid_status_constructs_successfully(status):
    suggestion = _make_suggestion(status=status)
    assert suggestion.status == status


def test_invalid_status_raises():
    with pytest.raises(InvalidSuggestionStatusError):
        _make_suggestion(status="merged")


@pytest.mark.parametrize("score", [0.0, 1.0, 0.5])
def test_valid_similarity_score_constructs_successfully(score):
    suggestion = _make_suggestion(similarity_score=score)
    assert suggestion.similarity_score == score


@pytest.mark.parametrize("score", [-0.01, 1.01, -5, 5])
def test_invalid_similarity_score_raises(score):
    with pytest.raises(InvalidSimilarityScoreError):
        _make_suggestion(similarity_score=score)
