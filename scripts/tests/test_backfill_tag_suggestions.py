"""T057: Tests for backfill_tag_suggestions.py."""
import uuid
import pytest
from unittest.mock import MagicMock, patch
from collections import defaultdict


def test_suggestions_created_for_similar_pairs():
    """Tag pairs with similarity above threshold should create suggestions."""
    from scripts.backfill_tag_suggestions import main

    session = MagicMock()

    tag1 = MagicMock()
    tag1.id = uuid.uuid4()
    tag1.name = "real time sync"
    tag1.tag_group_id = uuid.uuid4()
    tag1.embedding = [0.1] * 768

    tag2 = MagicMock()
    tag2.id = uuid.uuid4()
    tag2.name = "real-time sync"
    tag2.tag_group_id = tag1.tag_group_id
    tag2.embedding = [0.2] * 768

    # Mock query for tags with embeddings
    session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [tag1, tag2]
    # Mock existing suggestions query
    session.execute.return_value.fetchall.return_value = []

    mock_repo = MagicMock()
    similar_tag_data = MagicMock()
    similar_tag_data.id = tag2.id
    similar_tag_data.name = tag2.name
    mock_repo.find_similar.return_value = [(similar_tag_data, 0.92)]
    mock_repo.save_suggestion = MagicMock()

    with patch("src.infrastructure.persistence.database.init_db"):
        with patch("src.infrastructure.persistence.database.get_session", return_value=session):
            with patch("src.infrastructure.persistence.intelligence.tag_repo_impl.SqlAlchemyTagRepository", return_value=mock_repo):
                with patch("src.modules.intelligence.domain.entities.tag_normalization_suggestion.TagNormalizationSuggestion"):
                    with pytest.MonkeyPatch().context() as mp:
                        mp.setattr("sys.argv", ["backfill_tag_suggestions.py"])
                        main()

    mock_repo.save_suggestion.assert_called()


def test_suggestions_created_even_above_auto_merge_threshold():
    """Pairs above auto_merge threshold are still recorded as suggestions (not auto-merged)."""
    from scripts.backfill_tag_suggestions import main

    session = MagicMock()

    tag1 = MagicMock()
    tag1.id = uuid.uuid4()
    tag1.name = "deep learning"
    tag1.tag_group_id = uuid.uuid4()
    tag1.embedding = [0.5] * 768

    tag2 = MagicMock()
    tag2.id = uuid.uuid4()
    tag2.name = "Deep Learning"
    tag2.tag_group_id = tag1.tag_group_id
    tag2.embedding = [0.5] * 768

    session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [tag1, tag2]
    session.execute.return_value.fetchall.return_value = []

    mock_repo = MagicMock()
    similar_tag_data = MagicMock()
    similar_tag_data.id = tag2.id
    similar_tag_data.name = tag2.name
    # Very high similarity (above default auto_merge_threshold of 0.92)
    mock_repo.find_similar.return_value = [(similar_tag_data, 0.97)]
    mock_repo.save_suggestion = MagicMock()

    with patch("src.infrastructure.persistence.database.init_db"):
        with patch("src.infrastructure.persistence.database.get_session", return_value=session):
            with patch("src.infrastructure.persistence.intelligence.tag_repo_impl.SqlAlchemyTagRepository", return_value=mock_repo):
                with patch("src.modules.intelligence.domain.entities.tag_normalization_suggestion.TagNormalizationSuggestion"):
                    with pytest.MonkeyPatch().context() as mp:
                        mp.setattr("sys.argv", ["backfill_tag_suggestions.py"])
                        main()

    # Even with 0.97 similarity, a suggestion should be created (admin review)
    mock_repo.save_suggestion.assert_called()


def test_dry_run_does_not_save():
    """In dry-run mode, no suggestions should be persisted."""
    from scripts.backfill_tag_suggestions import main

    session = MagicMock()

    tag1 = MagicMock()
    tag1.id = uuid.uuid4()
    tag1.name = "test"
    tag1.tag_group_id = uuid.uuid4()
    tag1.embedding = [0.1] * 768

    tag2 = MagicMock()
    tag2.id = uuid.uuid4()
    tag2.name = "Test"
    tag2.tag_group_id = tag1.tag_group_id
    tag2.embedding = [0.2] * 768

    session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [tag1, tag2]
    session.execute.return_value.fetchall.return_value = []

    mock_repo = MagicMock()
    similar_tag_data = MagicMock()
    similar_tag_data.id = tag2.id
    similar_tag_data.name = tag2.name
    mock_repo.find_similar.return_value = [(similar_tag_data, 0.90)]

    with patch("src.infrastructure.persistence.database.init_db"):
        with patch("src.infrastructure.persistence.database.get_session", return_value=session):
            with patch("src.infrastructure.persistence.intelligence.tag_repo_impl.SqlAlchemyTagRepository", return_value=mock_repo):
                with pytest.MonkeyPatch().context() as mp:
                    mp.setattr("sys.argv", ["backfill_tag_suggestions.py", "--dry-run"])
                    main()

    mock_repo.save_suggestion.assert_not_called()
    session.commit.assert_not_called()


def test_skips_existing_pairs():
    """Pairs already in tag_normalization_suggestions should be skipped."""
    from scripts.backfill_tag_suggestions import main

    session = MagicMock()

    tag1_id = uuid.uuid4()
    tag2_id = uuid.uuid4()

    tag1 = MagicMock()
    tag1.id = tag1_id
    tag1.name = "test"
    tag1.tag_group_id = uuid.uuid4()
    tag1.embedding = [0.1] * 768

    tag2 = MagicMock()
    tag2.id = tag2_id
    tag2.name = "Test"
    tag2.tag_group_id = tag1.tag_group_id
    tag2.embedding = [0.2] * 768

    session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [tag1, tag2]
    # Existing suggestion pair
    session.execute.return_value.fetchall.return_value = [
        (str(min(tag1_id, tag2_id)), str(max(tag1_id, tag2_id))),
    ]

    mock_repo = MagicMock()
    similar_tag_data = MagicMock()
    similar_tag_data.id = tag2_id
    similar_tag_data.name = tag2.name
    mock_repo.find_similar.return_value = [(similar_tag_data, 0.90)]

    with patch("src.infrastructure.persistence.database.init_db"):
        with patch("src.infrastructure.persistence.database.get_session", return_value=session):
            with patch("src.infrastructure.persistence.intelligence.tag_repo_impl.SqlAlchemyTagRepository", return_value=mock_repo):
                with pytest.MonkeyPatch().context() as mp:
                    mp.setattr("sys.argv", ["backfill_tag_suggestions.py"])
                    main()

    # Should not save because pair already exists
    mock_repo.save_suggestion.assert_not_called()
