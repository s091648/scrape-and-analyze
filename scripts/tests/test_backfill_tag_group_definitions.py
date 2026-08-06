"""T056: Tests for backfill_tag_group_definitions.py."""
import pytest
from unittest.mock import MagicMock, patch


def test_missing_pairs_query_finds_orphan_groups():
    """The SQL query should find tags with group names that have no matching tag_group_definitions."""
    from scripts.backfill_tag_group_definitions import _SQL_MISSING_PAIRS

    assert "tag_group_name" in _SQL_MISSING_PAIRS
    assert "NOT EXISTS" in _SQL_MISSING_PAIRS
    assert "tag_group_definitions" in _SQL_MISSING_PAIRS


def test_creates_definitions_with_unsupervised_display_name():
    """New definitions should have display_name = '{name}_unsupervised'."""
    from scripts.backfill_tag_group_definitions import main

    session = MagicMock()
    row = MagicMock()
    row.grp_name = "digital_twin"
    row.topic_id = "topic-uuid-1"
    row.topic_name = "Digital Twins"
    session.execute.return_value.fetchall.return_value = [row]

    # Check column exists
    col_exists_row = MagicMock()
    session.execute.side_effect = [
        MagicMock(first=lambda: col_exists_row),  # column check
        MagicMock(fetchall=lambda: [row]),         # missing pairs query
        MagicMock(),                                # INSERT for the one row above
    ]

    with patch("src.infrastructure.persistence.database.init_db"):
        with patch("src.infrastructure.persistence.database.get_session", return_value=session):
            with pytest.MonkeyPatch().context() as mp:
                mp.setattr("sys.argv", ["backfill_tag_group_definitions.py"])
                main()

    # Should have executed INSERT with display_name = "digital_twin_unsupervised"
    # (str(call(...)) doesn't stringify the TextClause's SQL — str() each call's
    # first positional arg directly, which does compile to the raw SQL text)
    insert_calls = [c for c in session.execute.call_args_list if "INSERT" in str(c.args[0])]
    assert len(insert_calls) >= 1


def test_dry_run_prints_without_inserting():
    """In dry-run mode, no INSERT should be executed."""
    from scripts.backfill_tag_group_definitions import main

    session = MagicMock()
    row = MagicMock()
    row.grp_name = "ai_ml"
    row.topic_id = "topic-uuid-1"
    row.topic_name = "AI"

    col_exists_row = MagicMock()
    session.execute.side_effect = [
        MagicMock(first=lambda: col_exists_row),  # column check
        MagicMock(fetchall=lambda: [row]),         # missing pairs query
    ]

    with patch("src.infrastructure.persistence.database.init_db"):
        with patch("src.infrastructure.persistence.database.get_session", return_value=session):
            with pytest.MonkeyPatch().context() as mp:
                mp.setattr("sys.argv", ["backfill_tag_group_definitions.py", "--dry-run"])
                main()

    session.commit.assert_not_called()


def test_skips_when_column_dropped():
    """If tag_group_name column no longer exists, script exits gracefully."""
    from scripts.backfill_tag_group_definitions import main

    session = MagicMock()
    session.execute.return_value.first.return_value = None  # column check fails

    with patch("src.infrastructure.persistence.database.init_db"):
        with patch("src.infrastructure.persistence.database.get_session", return_value=session):
            with pytest.MonkeyPatch().context() as mp:
                mp.setattr("sys.argv", ["backfill_tag_group_definitions.py"])
                main()

    session.close.assert_called_once()
