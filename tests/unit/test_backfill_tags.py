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


def test_upsert_tags_dry_run_does_not_call_session(capsys):
    """dry_run=True must not execute any DB statements"""
    from scripts.backfill_tags import upsert_tags_for_article

    session = MagicMock()
    tag_groups = [{"group": "digital_twin", "tags": ["virtual replica", "real-time sync"]}]

    upsert_tags_for_article(session, "art-uuid", tag_groups, dry_run=True)

    session.execute.assert_not_called()
    out = capsys.readouterr().out
    assert "virtual replica" in out
    assert "real-time sync" in out


def test_upsert_tags_executes_three_statements_per_tag():
    """Each tag triggers INSERT tag, SELECT tag id, INSERT article_tag"""
    from scripts.backfill_tags import upsert_tags_for_article

    session = MagicMock()
    # SELECT returns a row with an id
    session.execute.return_value.first.return_value = ("tag-id-123",)

    tag_groups = [{"group": "digital_twin", "tags": ["virtual replica"]}]
    upsert_tags_for_article(session, "art-uuid", tag_groups, dry_run=False)

    assert session.execute.call_count == 3  # INSERT tag, SELECT id, INSERT article_tag


def test_upsert_tags_skips_empty_tag_names():
    """Tags with empty/None name must be silently skipped"""
    from scripts.backfill_tags import upsert_tags_for_article

    session = MagicMock()
    session.execute.return_value.first.return_value = ("tag-id",)

    tag_groups = [{"group": "digital_twin", "tags": ["", None, "valid-tag"]}]
    upsert_tags_for_article(session, "art-uuid", tag_groups, dry_run=False)

    # Only 1 valid tag → 3 execute calls
    assert session.execute.call_count == 3
