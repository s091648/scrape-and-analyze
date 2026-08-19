from unittest.mock import MagicMock

from src.modules.search.application.event_handlers.search_index_rebuild_handler import SearchIndexRebuildHandler


def test_handle_invokes_the_use_case():
    use_case = MagicMock()
    use_case.execute.return_value = {"article_count": 1, "topic_count": 1, "term_count": 2}
    handler = SearchIndexRebuildHandler(use_case)

    handler.handle(event=MagicMock())

    use_case.execute.assert_called_once()


def test_handle_never_raises_when_use_case_fails():
    use_case = MagicMock()
    use_case.execute.side_effect = RuntimeError("db down")
    handler = SearchIndexRebuildHandler(use_case)

    handler.handle(event=MagicMock())  # must not raise
