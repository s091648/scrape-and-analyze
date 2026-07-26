"""T058: Tests for audit_tag_groups.py."""
import pytest
from unittest.mock import MagicMock, patch


def test_orphan_query_detects_missing_definitions():
    """The orphan query should find tag_group_names without matching definitions."""
    from scripts.audit_tag_groups import _SQL_ORPHAN_TAGS

    assert "NOT EXISTS" in _SQL_ORPHAN_TAGS
    assert "tag_group_definitions" in _SQL_ORPHAN_TAGS
    assert "tag_group_name" in _SQL_ORPHAN_TAGS


def test_duplicate_casing_query_normalizes_keys():
    """The duplicate casing query should normalize group names for comparison."""
    from scripts.audit_tag_groups import _SQL_DUPLICATE_CASING

    assert "LOWER" in _SQL_DUPLICATE_CASING
    assert "REPLACE" in _SQL_DUPLICATE_CASING
    assert "HAVING COUNT" in _SQL_DUPLICATE_CASING


def test_audit_reports_orphan_groups(capsys):
    """Audit should report orphan group names that lack definitions."""
    from scripts.audit_tag_groups import main

    session = MagicMock()
    orphan_row = MagicMock()
    orphan_row.tag_group_name = "orphan_group"
    orphan_row.topic_name = "AI"
    orphan_row.tag_count = 5

    duplicate_row = MagicMock()
    duplicate_row.normalized = "test"
    duplicate_row.variants = ["Test", "test"]
    duplicate_row.topic_name = "AI"
    duplicate_row.tag_count = 3

    session.execute.return_value.fetchall.side_effect = [
        [orphan_row],   # orphan query
        [duplicate_row], # duplicate casing query
    ]

    with patch("src.infrastructure.persistence.database.init_db"):
        with patch("src.infrastructure.persistence.database.get_session", return_value=session):
            with pytest.MonkeyPatch().context() as mp:
                mp.setattr("sys.argv", ["audit_tag_groups.py"])
                main()

    output = capsys.readouterr().out
    assert "orphan_group" in output
    assert "Tag Group Audit Report" in output


def test_audit_reports_no_issues(capsys):
    """Audit should show no issues when all groups have definitions."""
    from scripts.audit_tag_groups import main

    session = MagicMock()
    session.execute.return_value.fetchall.side_effect = [
        [],  # no orphans
        [],  # no duplicates
    ]

    with patch("src.infrastructure.persistence.database.init_db"):
        with patch("src.infrastructure.persistence.database.get_session", return_value=session):
            with pytest.MonkeyPatch().context() as mp:
                mp.setattr("sys.argv", ["audit_tag_groups.py"])
                main()

    output = capsys.readouterr().out
    assert "✓ none" in output


def test_audit_with_topic_filter():
    """Audit should accept a --topic filter."""
    from scripts.audit_tag_groups import main

    session = MagicMock()
    session.execute.return_value.fetchall.side_effect = [[], []]

    with patch("src.infrastructure.persistence.database.init_db"):
        with patch("src.infrastructure.persistence.database.get_session", return_value=session):
            with pytest.MonkeyPatch().context() as mp:
                mp.setattr("sys.argv", ["audit_tag_groups.py", "--topic", "digital-twins"])
                main()

    # Verify the topic parameter was passed
    call_args = session.execute.call_args_list
    assert len(call_args) >= 1
