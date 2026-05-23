"""
scripts/data/runner.py
Core runner for versioned data migrations.

Version scripts live in scripts/data/versions/ and follow this interface:

    name: str          — unique key (same as filename without .py)
    description: str   — human-readable description
    requires_api: bool — True if the script calls external APIs (default False)

    def up(session) -> None:   ...   # required
    def down(session) -> None: ...   # optional
"""
import importlib.util
import sys
from pathlib import Path
from sqlalchemy import text

VERSIONS_DIR = Path(__file__).parent / "versions"


# ── Discovery ────────────────────────────────────────────────────────────────

def _load_version(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def discover_versions() -> list[tuple[str, object]]:
    """Return sorted list of (name, module) tuples from versions/."""
    scripts = sorted(VERSIONS_DIR.glob("[0-9]*.py"))
    return [(p.stem, _load_version(p)) for p in scripts]


# ── DB state helpers ─────────────────────────────────────────────────────────

def _ensure_table_exists(session) -> bool:
    row = session.execute(text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = 'data_migrations'"
    )).first()
    return row is not None


def get_executed(session) -> set[str]:
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
    versions = discover_versions()
    ran = 0

    for name, mod in versions:
        if name in executed:
            continue
        if getattr(mod, "requires_api", False) and not include_api:
            print(f"  [skip] {name}  (requires external API — use --include-api)")
            continue
        desc = getattr(mod, "description", "")
        print(f"  [run]  {name}")
        mod.up(session)
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
    versions = dict(discover_versions())

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

    desc = getattr(mod, "description", "")
    print(f"  [run]  {name}")
    mod.up(session)
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

    versions = dict(discover_versions())
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
    versions = discover_versions()

    if not versions:
        print("  No version scripts found in", VERSIONS_DIR)
        return

    print(f"\n{'STATUS':<12} {'NAME':<50} {'API?':<6} {'ALEMBIC REVISION':<40} DESCRIPTION")
    print("-" * 130)
    for name, mod in versions:
        status = "✓ executed" if name in executed else "○ pending"
        api_flag = "yes" if getattr(mod, "requires_api", False) else ""
        alembic_rev = getattr(mod, "alembic_revision", "")
        desc = getattr(mod, "description", "")
        print(f"{status:<12} {name:<50} {api_flag:<6} {alembic_rev:<40} {desc}")
    print()
