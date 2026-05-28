"""Unit tests for SqlAlchemyTagGroupDefinitionRepository."""
import uuid
from unittest.mock import MagicMock, patch, call

import pytest

from src.infrastructure.persistence.intelligence.tag_group_definition_repo_impl import (
    SqlAlchemyTagGroupDefinitionRepository,
)


@pytest.fixture
def session():
    return MagicMock()


@pytest.fixture
def repo(session):
    return SqlAlchemyTagGroupDefinitionRepository(session)


class TestFindByTopicId:
    @patch('src.infrastructure.persistence.intelligence.tag_group_definition_repo_impl.TagGroupDefinition', create=True)
    def test_returns_empty_when_no_rows(self, mock_model, repo, session):
        session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []
        topic_id = uuid.uuid4()
        result = repo.find_by_topic_id(topic_id)
        assert result == []
        session.query.return_value.filter_by.assert_called_once_with(topic_id=topic_id)

    @patch('src.infrastructure.persistence.intelligence.tag_group_definition_repo_impl.TagGroupDefinition', create=True)
    def test_maps_rows_to_data(self, mock_model, repo, session):
        row1 = MagicMock()
        row1.name = 'ai_ml'
        row1.display_name = 'AI & ML'
        row1.description = 'AI topics'
        session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [row1]

        topic_id = uuid.uuid4()
        result = repo.find_by_topic_id(topic_id)
        assert len(result) == 1
        assert result[0].name == 'ai_ml'
        assert result[0].display_name == 'AI & ML'
        assert result[0].description == 'AI topics'


class TestUpsert:
    def test_creates_new_record_when_not_existing(self, repo, session):
        session.query.return_value.filter_by.return_value.first.return_value = None
        topic_id = uuid.uuid4()
        repo.upsert('new_group', 'New Group', topic_id, description='desc')
        session.add.assert_called_once()
        session.flush.assert_called_once()

    def test_skips_insert_when_already_exists_without_embedding(self, repo, session):
        existing = MagicMock()
        existing.embedding = None
        session.query.return_value.filter_by.return_value.first.return_value = existing
        topic_id = uuid.uuid4()
        repo.upsert('existing', 'Existing', topic_id)
        session.add.assert_not_called()

    def test_updates_embedding_when_existing_has_none(self, repo, session):
        existing = MagicMock()
        existing.id = uuid.uuid4()
        existing.embedding = None
        session.query.return_value.filter_by.return_value.first.return_value = existing
        topic_id = uuid.uuid4()
        embedding = [0.1, 0.2, 0.3]
        repo.upsert('existing', 'Existing', topic_id, embedding=embedding)
        session.execute.assert_called_once()
        call_args = session.execute.call_args
        assert 'vector' in call_args[0][0]

    def test_does_not_update_embedding_when_existing_already_has_one(self, repo, session):
        existing = MagicMock()
        existing.embedding = [0.5, 0.6]
        session.query.return_value.filter_by.return_value.first.return_value = existing
        topic_id = uuid.uuid4()
        embedding = [0.1, 0.2, 0.3]
        repo.upsert('existing', 'Existing', topic_id, embedding=embedding)
        session.execute.assert_not_called()

    def test_sets_embedding_on_new_record(self, repo, session):
        session.query.return_value.filter_by.return_value.first.return_value = None
        new_record = MagicMock()
        new_record.id = uuid.uuid4()
        # Mock TagGroupDefinition constructor to return our mock
        with patch('src.infrastructure.persistence.intelligence.tag_group_definition_repo_impl.TagGroupDefinition') as MockModel:
            MockModel.return_value = new_record
            topic_id = uuid.uuid4()
            embedding = [0.1, 0.2]
            repo.upsert('new', 'New', topic_id, embedding=embedding)
            session.add.assert_called_once_with(new_record)
            session.execute.assert_called_once()
