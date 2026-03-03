import pytest
from unittest.mock import MagicMock


def test_find_articles_returns_rows():
    """find_articles_needing_backfill returns all rows from session"""
    from scripts.backfill_tags import find_articles_needing_backfill

    session = MagicMock()
    session.execute.return_value.fetchall.return_value = [
        MagicMock(id="art-1", title="T1", content="C1", analysis_id="an-1"),
    ]

    rows = find_articles_needing_backfill(session)

    assert len(rows) == 1
    session.execute.assert_called_once()


def test_find_articles_passes_limit():
    """find_articles_needing_backfill passes limit to query when given"""
    from scripts.backfill_tags import find_articles_needing_backfill

    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []

    find_articles_needing_backfill(session, limit=5)

    call_args = session.execute.call_args
    # limit value must appear in the params dict
    assert call_args[0][1] == {"limit": 5}


def test_find_articles_no_limit_omits_param():
    """find_articles_needing_backfill omits params when no limit"""
    from scripts.backfill_tags import find_articles_needing_backfill

    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []

    find_articles_needing_backfill(session, limit=None)

    call_args = session.execute.call_args
    # called with just the text object, no params dict
    assert len(call_args[0]) == 1
