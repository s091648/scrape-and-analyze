"""Tests for scripts/data/versions/002_backfill_arxiv_id.py.

The filename starts with a digit, so it can't be imported with a normal
`import` statement — loaded the same way scripts/data/runner.py's own
discovery does (importlib.util.spec_from_file_location by path)."""
from unittest.mock import MagicMock

from scripts.data.runner import VERSIONS_DIR, _load_version

migration = _load_version(VERSIONS_DIR / "002_backfill_arxiv_id.py")


def _row(id_, arxiv_id):
    row = MagicMock()
    row.id = id_
    row.arxiv_id = arxiv_id
    return row


def test_module_declares_correct_chain_metadata():
    assert migration.name == "002_backfill_arxiv_id"
    assert migration.down_revision == "001_backfill_tag_group_definitions"
    assert migration.requires_api is False
    assert migration.alembic_revision is None


def test_query_only_matches_url_form_arxiv_ids():
    assert "LIKE 'http%'" in migration._SQL_URL_FORM_ARXIV_IDS
    assert "arxiv_id" in migration._SQL_URL_FORM_ARXIV_IDS


def test_up_normalizes_url_form_arxiv_ids_and_commits():
    session = MagicMock()
    rows = [
        _row("article-1", "http://arxiv.org/abs/2606.29232v1"),
        _row("article-2", "https://arxiv.org/abs/2101.00001"),
    ]
    session.execute.return_value.fetchall.return_value = rows

    migration.up(session)

    update_calls = [c for c in session.execute.call_args_list if "UPDATE articles" in str(c.args[0])]
    assert len(update_calls) == 2
    assert update_calls[0].args[1] == {"normalized": "2606.29232", "id": "article-1"}
    assert update_calls[1].args[1] == {"normalized": "2101.00001", "id": "article-2"}
    session.commit.assert_called_once()


def test_up_is_noop_when_nothing_pending():
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []

    migration.up(session)

    update_calls = [c for c in session.execute.call_args_list if "UPDATE articles" in str(c.args[0])]
    assert update_calls == []
    session.commit.assert_not_called()


def test_up_skips_rows_normalize_leaves_unchanged():
    """Defence-in-depth: even if the SQL filter's LIKE 'http%' ever matched a row
    normalize_arxiv_id() doesn't actually change, up() must not issue a no-op UPDATE."""
    session = MagicMock()
    # Already-bare id that happens to satisfy LIKE 'http%' would be unusual, but
    # verify the Python-side guard independently of the SQL filter.
    rows = [_row("article-3", "2606.29232")]
    session.execute.return_value.fetchall.return_value = rows

    migration.up(session)

    update_calls = [c for c in session.execute.call_args_list if "UPDATE articles" in str(c.args[0])]
    assert update_calls == []
    session.commit.assert_called_once()
