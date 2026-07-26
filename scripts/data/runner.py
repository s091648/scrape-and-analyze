"""
scripts/data/runner.py
Core runner for versioned data migrations.

Version scripts live in scripts/data/versions/ and follow this interface:

    name: str                        — unique key (same as filename without .py)
    description: str                 — human-readable description
    requires_api: bool               — True if the script calls external APIs (default False)
    down_revision: Optional[str]     — the `name` of the migration this one runs after;
                                        None marks this migration as the chain's root
                                        (exactly one migration in versions/ may be root).
                                        Replaces the old numeric-filename-prefix ordering —
                                        execution order is the root-first walk of this chain,
                                        not filename/discovery order.
    alembic_revision: Optional[str]  — the Alembic schema revision that must already be
                                        applied (at or before the database's current position)
                                        before this migration may run. This is a *reachability*
                                        precondition checked live against the database's actual
                                        current Alembic revision at execution time — it is never
                                        persisted anywhere. None means no schema precondition.

    def up(session) -> None:   ...   # required
    def down(session) -> None: ...   # optional, manual reversal only — never auto-invoked
"""
import importlib.util
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import text

VERSIONS_DIR = Path(__file__).parent / "versions"
REPO_ROOT = Path(__file__).resolve().parents[2]


class MigrationChainError(Exception):
    """Raised when scripts/data/versions/ does not form a single, valid, linear
    down_revision chain (missing predecessor, forked predecessor, or a
    cycle/gap that leaves migrations unreachable from the chain's root)."""


# ── Discovery & chain resolution ────────────────────────────────────────────

def _load_version(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _discover_raw() -> dict:
    """Load every version script module in versions/, keyed by its declared `name`
    (not by filename — filenames are free-form/descriptive and no longer load-bearing)."""
    modules = {}
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        if path.stem == "__init__":
            continue
        mod = _load_version(path)
        mod_name = getattr(mod, "name", path.stem)
        modules[mod_name] = mod
    return modules


def _resolve_chain(modules: dict) -> list:
    """Validate that `modules` forms exactly one linear down_revision chain and
    return the root-first execution order as a list of (name, module) tuples.

    Validates: exactly one root (down_revision=None), every non-root
    down_revision references an existing migration, no two migrations declare
    the same down_revision (fork), and every migration is reachable from the
    root (catches cycles/gaps, which can only ever form a disconnected
    component once forks are ruled out — see research.md for the proof)."""
    if not modules:
        return []

    roots = [name for name, mod in modules.items() if getattr(mod, "down_revision", None) is None]
    if len(roots) != 1:
        raise MigrationChainError(
            f"expected exactly one root migration (down_revision=None), found {len(roots)}: {sorted(roots)}"
        )

    children_by_parent = {}
    for name, mod in modules.items():
        parent = getattr(mod, "down_revision", None)
        if parent is None:
            continue
        if parent not in modules:
            raise MigrationChainError(
                f"migration '{name}' declares down_revision='{parent}', which does not exist"
            )
        if parent in children_by_parent:
            raise MigrationChainError(
                f"chain is forked — both '{children_by_parent[parent]}' and '{name}' declare "
                f"down_revision='{parent}'"
            )
        children_by_parent[parent] = name

    ordered = []
    current = roots[0]
    while current is not None:
        ordered.append((current, modules[current]))
        current = children_by_parent.get(current)

    if len(ordered) != len(modules):
        unreached = sorted(set(modules) - {name for name, _ in ordered})
        raise MigrationChainError(
            f"migration chain does not reach all known migrations — unreachable from root "
            f"(check for a cycle or a gap): {unreached}"
        )

    return ordered


def discover_versions() -> list:
    """Return the validated, root-first execution order of all version scripts
    in versions/. Raises MigrationChainError if the chain is invalid."""
    return _resolve_chain(_discover_raw())


def _safe_discover_versions() -> list:
    """CLI-facing wrapper: prints and exits non-zero on an invalid chain instead
    of letting MigrationChainError propagate as an unhandled traceback."""
    try:
        return discover_versions()
    except MigrationChainError as e:
        print(f"ERROR: {e}")
        sys.exit(1)


# ── Alembic schema-state precondition ───────────────────────────────────────

def _alembic_revision_satisfied(connection, required_revision: str) -> bool:
    """Return whether `required_revision` has already been applied (is at or
    before the database's actual current Alembic revision), walking the real
    Alembic revision graph backward from the database's current head(s). This
    is a reachability check, not an exact-transition match — a data migration
    may be deployed long after its declared schema requirement, by which point
    the database's head may have moved many revisions further."""
    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext

    cfg = AlembicConfig(str(REPO_ROOT / "alembic.ini"))
    script_dir = ScriptDirectory.from_config(cfg)
    context = MigrationContext.configure(connection)

    visited = set()
    stack = list(context.get_current_heads())
    while stack:
        rev = stack.pop()
        if rev is None or rev in visited:
            continue
        if rev == required_revision:
            return True
        visited.add(rev)
        revision_obj = script_dir.get_revision(rev)
        if revision_obj is None:
            continue
        down = revision_obj.down_revision
        if down is None:
            continue
        if isinstance(down, (list, tuple)):
            stack.extend(down)
        else:
            stack.append(down)
    return False


def _current_alembic_revision_display(connection) -> str:
    """Human-readable current Alembic revision(s), for precondition error messages."""
    from alembic.runtime.migration import MigrationContext

    context = MigrationContext.configure(connection)
    heads = context.get_current_heads()
    return ", ".join(heads) if heads else "(none — no schema migrations applied)"


def _check_alembic_precondition(session, name: str, mod) -> Optional[str]:
    """Return an error message if `mod`'s declared alembic_revision precondition
    is not satisfied, else None. Scripts with alembic_revision=None always pass."""
    required = getattr(mod, "alembic_revision", None)
    if required is None:
        return None
    connection = session.connection()
    if _alembic_revision_satisfied(connection, required):
        return None
    current = _current_alembic_revision_display(connection)
    return (
        f"{name} requires alembic schema revision '{required}' to already be applied; "
        f"current database revision is '{current}'. Refusing to execute."
    )


# ── DB state helpers ─────────────────────────────────────────────────────────

def _ensure_table_exists(session) -> bool:
    row = session.execute(text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = 'data_migrations'"
    )).first()
    return row is not None


def get_executed(session) -> set:
    return {
        row[0]
        for row in session.execute(text(
            "SELECT name FROM data_migrations WHERE rolled_back_at IS NULL"
        )).fetchall()
    }


def _record_executed(session, name: str, description: str) -> None:
    session.execute(
        text("INSERT INTO data_migrations (name, description) VALUES (:n, :d)"),
        {"n": name, "d": description},
    )
    session.commit()


def _record_rolled_back(session, name: str) -> None:
    session.execute(
        text("UPDATE data_migrations SET rolled_back_at = NOW() WHERE name = :n"),
        {"n": name},
    )
    session.commit()


# ── Commands ─────────────────────────────────────────────────────────────────

def run_pending(session, include_api: bool = False) -> None:
    if not _ensure_table_exists(session):
        print("ERROR: data_migrations table not found. Run: make migrate")
        sys.exit(1)

    executed = get_executed(session)
    versions = _safe_discover_versions()
    ran = 0

    for name, mod in versions:
        if name in executed:
            continue
        if getattr(mod, "requires_api", False) and not include_api:
            print(f"  [skip] {name}  (requires external API — use --include-api)")
            continue

        precondition_error = _check_alembic_precondition(session, name, mod)
        if precondition_error:
            print(f"ERROR: {precondition_error}")
            sys.exit(1)

        desc = getattr(mod, "description", "")
        print(f"  [run]  {name}")
        try:
            mod.up(session)
        except Exception as e:
            session.rollback()
            print(f"ERROR: {name} failed and was rolled back: {e}")
            sys.exit(1)
        _record_executed(session, name, desc)
        print(f"  [done] {name}")
        ran += 1

    if ran == 0:
        print("  No pending data migrations.")


def run_one(session, name: str, include_api: bool = False) -> None:
    if not _ensure_table_exists(session):
        print("ERROR: data_migrations table not found. Run: make migrate")
        sys.exit(1)

    executed = get_executed(session)
    versions = dict(_safe_discover_versions())

    if name not in versions:
        print(f"ERROR: '{name}' not found in {VERSIONS_DIR}")
        sys.exit(1)

    if name in executed:
        print(f"  [skip] {name} already executed")
        return

    mod = versions[name]
    if getattr(mod, "requires_api", False) and not include_api:
        print(f"  [skip] {name} requires external API — use --include-api")
        return

    precondition_error = _check_alembic_precondition(session, name, mod)
    if precondition_error:
        print(f"ERROR: {precondition_error}")
        sys.exit(1)

    desc = getattr(mod, "description", "")
    print(f"  [run]  {name}")
    try:
        mod.up(session)
    except Exception as e:
        session.rollback()
        print(f"ERROR: {name} failed and was rolled back: {e}")
        sys.exit(1)
    _record_executed(session, name, desc)
    print(f"  [done] {name}")


def run_down(session, name: str) -> None:
    if not _ensure_table_exists(session):
        print("ERROR: data_migrations table not found. Run: make migrate")
        sys.exit(1)

    executed = get_executed(session)
    if name not in executed:
        print(f"  [skip] '{name}' is not in the executed set")
        return

    versions = dict(_safe_discover_versions())
    if name not in versions:
        print(f"ERROR: '{name}' not found in {VERSIONS_DIR}")
        sys.exit(1)

    mod = versions[name]
    if not hasattr(mod, "down"):
        print(f"ERROR: '{name}' has no down() function")
        sys.exit(1)

    print(f"  [down] {name}")
    mod.down(session)
    _record_rolled_back(session, name)
    print(f"  [done] {name} rolled back")


def list_status(session) -> None:
    if not _ensure_table_exists(session):
        print("ERROR: data_migrations table not found. Run: make migrate")
        sys.exit(1)

    executed = get_executed(session)
    versions = _safe_discover_versions()

    if not versions:
        print("  No version scripts found in", VERSIONS_DIR)
        return

    print(f"\n{'STATUS':<12} {'NAME':<50} {'API?':<6} {'ALEMBIC REVISION':<40} DESCRIPTION")
    print("-" * 130)
    for name, mod in versions:
        status = "✓ executed" if name in executed else "○ pending"
        api_flag = "yes" if getattr(mod, "requires_api", False) else ""
        alembic_rev = getattr(mod, "alembic_revision", None) or ""
        desc = getattr(mod, "description", "")
        print(f"{status:<12} {name:<50} {api_flag:<6} {alembic_rev:<40} {desc}")
    print()
