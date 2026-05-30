"""Unit tests for SqlAlchemyTagRepository."""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.persistence.intelligence.tag_repo_impl import SqlAlchemyTagRepository
from src.modules.intelligence.domain.entities.tag_normalization_suggestion import TagNormalizationSuggestion


@pytest.fixture
def session():
    return MagicMock()


@pytest.fixture
def repo(session):
    return SqlAlchemyTagRepository(session)


class TestFindByGroup:
    def test_returns_empty_when_no_matches(self, repo, session):
        session.query.return_value.join.return_value.filter.return_value.all.return_value = []
        result = repo.find_by_group('nonexistent', uuid.uuid4())
        assert result == []

    def test_maps_rows_to_tag_data(self, repo, session):
        tag_row = MagicMock()
        tag_row.id = uuid.uuid4()
        tag_row.name = 'Transformer'
        group_def = MagicMock()
        group_def.name = 'ai_ml'
        tag_row.group_def = group_def
        tag_row.embedding = [0.1, 0.2]
        session.query.return_value.join.return_value.filter.return_value.all.return_value = [tag_row]
        result = repo.find_by_group('ai_ml', uuid.uuid4())
        assert len(result) == 1
        assert result[0].name == 'Transformer'
        assert result[0].tag_group_name == 'ai_ml'
        assert result[0].embedding == [0.1, 0.2]

    def test_handles_none_embedding(self, repo, session):
        tag_row = MagicMock()
        tag_row.id = uuid.uuid4()
        tag_row.name = 'Test'
        group_def = MagicMock()
        group_def.name = 'g1'
        tag_row.group_def = group_def
        tag_row.embedding = None
        session.query.return_value.join.return_value.filter.return_value.all.return_value = [tag_row]
        result = repo.find_by_group('g1', uuid.uuid4())
        assert result[0].embedding is None


class TestFindSimilar:
    def test_returns_empty_when_topic_id_is_none(self, repo, session):
        result = repo.find_similar([0.1], 'group', None, 0.8)
        assert result == []

    def test_queries_with_vector_and_threshold(self, repo, session):
        row = (uuid.uuid4(), 'Transformer', 'ai_ml', 0.95)
        session.execute.return_value.fetchall.return_value = [row]
        result = repo.find_similar([0.1] * 768, 'ai_ml', uuid.uuid4(), 0.8)
        assert len(result) == 1
        tag_data, score = result[0]
        assert tag_data.name == 'Transformer'
        assert score == 0.95


class TestSave:
    def test_raises_when_topic_id_is_none(self, repo, session):
        with pytest.raises(ValueError, match="topic_id is required"):
            repo.save('tag', 'group', [0.1], None)

    def test_raises_when_group_not_found(self, repo, session):
        session.query.return_value.filter_by.return_value.first.return_value = None
        with pytest.raises(ValueError, match="Tag group 'missing' not found"):
            repo.save('tag', 'missing', [0.1], uuid.uuid4())

    def test_creates_new_tag_when_not_existing(self, repo, session):
        group = MagicMock()
        group.id = uuid.uuid4()
        # First .filter_by() for group lookup, second for tag lookup
        session.query.return_value.filter_by.return_value.first.side_effect = [group, None]
        topic_id = uuid.uuid4()
        result = repo.save('new_tag', 'ai_ml', [0.1] * 768, topic_id)
        session.add.assert_called_once()
        session.execute.assert_called_once()
        assert result.name == 'new_tag'

    def test_updates_embedding_on_existing_tag(self, repo, session):
        group = MagicMock()
        group.id = uuid.uuid4()
        existing_tag = MagicMock()
        existing_tag.id = uuid.uuid4()
        existing_tag.name = 'existing'
        session.query.return_value.filter_by.return_value.first.side_effect = [group, existing_tag]
        result = repo.save('existing', 'ai_ml', [0.1] * 768, uuid.uuid4())
        session.add.assert_not_called()
        session.execute.assert_called_once()
        assert result.name == 'existing'


class TestLinkToArticle:
    def test_links_tag_to_article(self, repo, session):
        article = MagicMock()
        article.tags = []
        tag = MagicMock()
        session.query.return_value.filter_by.return_value.first.side_effect = [article, tag]
        repo.link_to_article(uuid.uuid4(), uuid.uuid4())
        # tag not in article.tags, so append is called
        assert tag in article.tags

    def test_skips_if_tag_already_linked(self, repo, session):
        tag = MagicMock()
        article = MagicMock()
        article.tags = [tag]
        session.query.return_value.filter_by.return_value.first.side_effect = [article, tag]
        repo.link_to_article(uuid.uuid4(), uuid.uuid4())
        # tag already in article.tags, so no append


class TestSaveSuggestion:
    def test_saves_and_returns_with_id(self, repo, session):
        suggestion = TagNormalizationSuggestion(
            new_tag_id=uuid.uuid4(),
            existing_tag_id=uuid.uuid4(),
            similarity_score=0.9,
            article_id=uuid.uuid4(),
            status='pending',
        )
        mock_row = MagicMock()
        mock_row.id = uuid.uuid4()
        with patch('models.tag_normalization_suggestion.TagNormalizationSuggestion', return_value=mock_row):
            result = repo.save_suggestion(suggestion)
        session.add.assert_called_once()
        session.flush.assert_called_once()
        assert result.id == mock_row.id


class TestListPendingSuggestions:
    def test_returns_pending_suggestions(self, repo, session):
        row = MagicMock()
        row.id = uuid.uuid4()
        row.new_tag_id = uuid.uuid4()
        row.existing_tag_id = uuid.uuid4()
        row.similarity_score = 0.9
        row.status = 'pending'
        row.article_id = None
        session.query.return_value.filter_by.return_value.all.return_value = [row]
        result = repo.list_pending_suggestions()
        assert len(result) == 1
        assert result[0].status == 'pending'

    def test_returns_empty_when_none(self, repo, session):
        session.query.return_value.filter_by.return_value.all.return_value = []
        result = repo.list_pending_suggestions()
        assert result == []


class TestApproveSuggestion:
    def test_approves_and_cleans_up(self, repo, session):
        suggestion = MagicMock()
        suggestion.new_tag_id = uuid.uuid4()
        suggestion.existing_tag_id = uuid.uuid4()
        session.query.return_value.filter_by.return_value.first.return_value = suggestion
        suggestion_id = uuid.uuid4()
        resolved_by = uuid.uuid4()
        repo.approve_suggestion(suggestion_id, resolved_by)
        # Should execute 3 SQL statements: INSERT, DELETE article_tags, DELETE tag
        assert session.execute.call_count == 3

    def test_noop_when_suggestion_not_found(self, repo, session):
        session.query.return_value.filter_by.return_value.first.return_value = None
        repo.approve_suggestion(uuid.uuid4(), uuid.uuid4())
        session.execute.assert_not_called()

    # ── T038: Verify suggestion row is expunged from session ──────────────────

    def test_approve_suggestion_expunges_suggestion_from_session(self, repo, session):
        """approve_suggestion calls session.expunge on the suggestion before
        deleting the tag, detaching the ORM object so it won't be flushed."""
        suggestion = MagicMock()
        suggestion.new_tag_id = uuid.uuid4()
        suggestion.existing_tag_id = uuid.uuid4()
        session.query.return_value.filter_by.return_value.first.return_value = suggestion

        repo.approve_suggestion(uuid.uuid4(), uuid.uuid4())

        session.expunge.assert_called_once_with(suggestion)


class TestRejectSuggestion:
    def test_sets_status_to_rejected(self, repo, session):
        suggestion = MagicMock()
        suggestion.status = 'pending'
        session.query.return_value.filter_by.return_value.first.return_value = suggestion
        repo.reject_suggestion(uuid.uuid4(), uuid.uuid4())
        assert suggestion.status == 'rejected'
        assert suggestion.resolved_at is not None

    def test_noop_when_not_found(self, repo, session):
        session.query.return_value.filter_by.return_value.first.return_value = None
        repo.reject_suggestion(uuid.uuid4(), uuid.uuid4())
        # No crash


class TestCommit:
    def test_commits_successfully(self, repo, session):
        repo.commit()
        session.commit.assert_called_once()

    def test_rollbacks_on_failure(self, repo, session):
        session.commit.side_effect = Exception("db error")
        with pytest.raises(Exception, match="db error"):
            repo.commit()
        session.rollback.assert_called_once()
