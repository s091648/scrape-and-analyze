from unittest.mock import MagicMock, patch
from uuid import uuid4


def _make_setting(source_type="rss"):
    s = MagicMock()
    s.id = uuid4()
    s.name = "test-source"
    s.url = "https://example.com/feed"
    s.source_type = source_type
    s.selector_config = {}
    s.frequency = 24
    s.topic_id = uuid4()
    return s


def test_get_sources_due_includes_topic_id():
    from src.infrastructure.persistence.sqlalchemy_repos.scraper_setting_repo_impl import (
        get_sources_due,
    )
    setting = _make_setting()
    topic_mock = MagicMock()
    topic_mock.prompt_override = "Custom prompt."

    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = [setting]
    # topic lookup returns the topic mock
    session.query.return_value.filter_by.return_value.first.return_value = topic_mock

    with patch(
        "src.infrastructure.persistence.db.get_session",
        return_value=session,
    ):
        results = get_sources_due()

    assert len(results) == 1
    assert "topic_id" in results[0]
    assert results[0]["topic_id"] == str(setting.topic_id)
    assert results[0]["prompt_override"] == "Custom prompt."
