from unittest.mock import MagicMock
from uuid import uuid4


def _make_topic_row(name="digital-twins"):
    row = MagicMock()
    row.id = uuid4()
    row.name = name
    row.display_name = "Digital Twins"
    row.description = None
    row.color_hex = "#3B82F6"
    row.prompt_override = None
    row.sort_order = 1
    row.is_active = True
    row.created_at = None
    return row


def test_list_active_returns_entities():
    from src.infrastructure.persistence.shared.topic_repo_impl import (
        SqlAlchemyTopicRepository,
    )
    from src.shared.domain.entities import Topic
    row = _make_topic_row()
    session = MagicMock()
    session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [row]
    repo = SqlAlchemyTopicRepository(session=session)
    results = repo.list_active()
    assert len(results) == 1
    assert isinstance(results[0], Topic)
    assert results[0].name == "digital-twins"


def test_find_by_id_returns_none_when_not_found():
    from src.infrastructure.persistence.shared.topic_repo_impl import (
        SqlAlchemyTopicRepository,
    )
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = None
    repo = SqlAlchemyTopicRepository(session=session)
    assert repo.find_by_id(uuid4()) is None