"""Tests for scripts/data/runner.py — chain resolution, the Alembic schema-state
precondition gate, and transactional fail-fast execution semantics (019-cicd-data-migrations)."""
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from scripts.data import runner


def make_module(name, down_revision=None, alembic_revision=None,
                 requires_api=False, up=None, description=""):
    """Build an in-memory fake version-script module for tests, without touching
    the filesystem or scripts/data/versions/."""
    mod = types.ModuleType(name)
    mod.name = name
    mod.description = description or f"test migration {name}"
    mod.requires_api = requires_api
    mod.down_revision = down_revision
    mod.alembic_revision = alembic_revision
    mod.up = up if up is not None else (lambda session: None)
    return mod


def _mock_session_with_table():
    """A MagicMock session where _ensure_table_exists() is True and get_executed() is empty."""
    session = MagicMock()
    session.execute.return_value.first.return_value = ("data_migrations",)
    session.execute.return_value.fetchall.return_value = []
    return session


# ── Chain resolution (US2 — T008-T011) ──────────────────────────────────────

def test_linear_chain_executes_in_declared_order_not_alphabetical():
    charlie = make_module("charlie", down_revision=None)
    alpha = make_module("alpha", down_revision="charlie")
    bravo = make_module("bravo", down_revision="alpha")
    modules = {"charlie": charlie, "alpha": alpha, "bravo": bravo}

    ordered = runner._resolve_chain(modules)

    assert [name for name, _ in ordered] == ["charlie", "alpha", "bravo"]


def test_fork_detection_raises_naming_both_conflicting_migrations():
    root = make_module("root", down_revision=None)
    a = make_module("a", down_revision="root")
    b = make_module("b", down_revision="root")  # both claim `root` as predecessor
    modules = {"root": root, "a": a, "b": b}

    with pytest.raises(runner.MigrationChainError) as exc:
        runner._resolve_chain(modules)

    assert "a" in str(exc.value)
    assert "b" in str(exc.value)


def test_missing_predecessor_reference_raises_naming_it():
    root = make_module("root", down_revision=None)
    orphan = make_module("orphan", down_revision="does_not_exist")
    modules = {"root": root, "orphan": orphan}

    with pytest.raises(runner.MigrationChainError) as exc:
        runner._resolve_chain(modules)

    assert "does_not_exist" in str(exc.value)


def test_disconnected_cycle_is_rejected_as_unreachable():
    root = make_module("root", down_revision=None)
    ring_a = make_module("ring_a", down_revision="ring_b")
    ring_b = make_module("ring_b", down_revision="ring_a")
    modules = {"root": root, "ring_a": ring_a, "ring_b": ring_b}

    with pytest.raises(runner.MigrationChainError) as exc:
        runner._resolve_chain(modules)

    assert "ring_a" in str(exc.value)
    assert "ring_b" in str(exc.value)


# ── Fail-fast / rollback safety (US4 — T015-T019) ───────────────────────────

def test_failed_up_rolls_back_and_does_not_commit(monkeypatch):
    def failing_up(session):
        raise RuntimeError("boom")

    mod = make_module("bad", up=failing_up)
    monkeypatch.setattr(runner, "discover_versions", lambda: [("bad", mod)])
    session = _mock_session_with_table()

    with pytest.raises(SystemExit):
        runner.run_pending(session)

    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_failed_migration_is_not_recorded(monkeypatch):
    def failing_up(session):
        raise RuntimeError("boom")

    mod = make_module("bad", up=failing_up)
    monkeypatch.setattr(runner, "discover_versions", lambda: [("bad", mod)])
    record_mock = MagicMock()
    monkeypatch.setattr(runner, "_record_executed", record_mock)
    session = _mock_session_with_table()

    with pytest.raises(SystemExit):
        runner.run_pending(session)

    record_mock.assert_not_called()


def test_later_chained_migration_not_attempted_after_earlier_failure(monkeypatch):
    later_up = MagicMock()

    def failing_up(session):
        raise RuntimeError("boom")

    first = make_module("first", down_revision=None, up=failing_up)
    second = make_module("second", down_revision="first", up=later_up)
    monkeypatch.setattr(runner, "discover_versions", lambda: [("first", first), ("second", second)])
    session = _mock_session_with_table()

    with pytest.raises(SystemExit):
        runner.run_pending(session)

    later_up.assert_not_called()


def test_cli_exits_non_zero_when_migration_fails(monkeypatch):
    import scripts.run_data_migrations as cli

    monkeypatch.setattr(sys, "argv", ["run_data_migrations.py"])

    def failing_run_pending(session, include_api=False):
        sys.exit(1)

    with patch("src.infrastructure.persistence.database.init_db"), \
            patch("src.infrastructure.persistence.database.get_session", return_value=MagicMock()), \
            patch("scripts.data.runner.run_pending", side_effect=failing_run_pending):
        with pytest.raises(SystemExit) as exc:
            cli.main()

    assert exc.value.code == 1


def test_migration_failure_never_touches_alembic_upgrade_downgrade(monkeypatch):
    def failing_up(session):
        raise RuntimeError("boom")

    mod = make_module("bad", up=failing_up)
    monkeypatch.setattr(runner, "discover_versions", lambda: [("bad", mod)])
    session = _mock_session_with_table()

    with patch("alembic.command.upgrade") as mock_upgrade, \
            patch("alembic.command.downgrade") as mock_downgrade:
        with pytest.raises(SystemExit):
            runner.run_pending(session)

    mock_upgrade.assert_not_called()
    mock_downgrade.assert_not_called()


# ── Alembic schema-state precondition (US3 — T023-T025) ─────────────────────

def test_required_revision_not_yet_reached_is_refused():
    connection = MagicMock()
    fake_context = MagicMock()
    fake_context.get_current_heads.return_value = ("rev_b",)

    chain = {"rev_b": MagicMock(down_revision="rev_a"), "rev_a": MagicMock(down_revision=None)}
    fake_script_dir = MagicMock()
    fake_script_dir.get_revision.side_effect = lambda rev_id: chain.get(rev_id)

    with patch("alembic.config.Config"), \
            patch("alembic.script.ScriptDirectory.from_config", return_value=fake_script_dir), \
            patch("alembic.runtime.migration.MigrationContext.configure", return_value=fake_context):
        satisfied = runner._alembic_revision_satisfied(connection, "rev_c")

    assert satisfied is False


def test_required_revision_already_passed_several_revisions_ago():
    connection = MagicMock()
    fake_context = MagicMock()
    fake_context.get_current_heads.return_value = ("rev_d",)

    chain = {
        "rev_d": MagicMock(down_revision="rev_c"),
        "rev_c": MagicMock(down_revision="rev_b"),
        "rev_b": MagicMock(down_revision="rev_a"),
        "rev_a": MagicMock(down_revision=None),
    }
    fake_script_dir = MagicMock()
    fake_script_dir.get_revision.side_effect = lambda rev_id: chain.get(rev_id)

    with patch("alembic.config.Config"), \
            patch("alembic.script.ScriptDirectory.from_config", return_value=fake_script_dir), \
            patch("alembic.runtime.migration.MigrationContext.configure", return_value=fake_context):
        satisfied = runner._alembic_revision_satisfied(connection, "rev_a")

    assert satisfied is True


def test_no_declared_requirement_skips_check_entirely(monkeypatch):
    called = MagicMock()
    monkeypatch.setattr(runner, "_alembic_revision_satisfied", called)
    mod = make_module("no_req", alembic_revision=None)
    session = MagicMock()

    error = runner._check_alembic_precondition(session, "no_req", mod)

    assert error is None
    called.assert_not_called()


# ── Automatic-run gating (US1 — T029-T030) ──────────────────────────────────

def test_requires_api_migration_skipped_by_default(monkeypatch):
    api_up = MagicMock()
    mod = make_module("api_thing", requires_api=True, up=api_up)
    monkeypatch.setattr(runner, "discover_versions", lambda: [("api_thing", mod)])
    session = _mock_session_with_table()

    runner.run_pending(session, include_api=False)

    api_up.assert_not_called()


def test_no_pending_migrations_is_a_noop_success(monkeypatch, capsys):
    monkeypatch.setattr(runner, "discover_versions", lambda: [])
    session = _mock_session_with_table()

    runner.run_pending(session)

    captured = capsys.readouterr()
    assert "No pending data migrations" in captured.out
