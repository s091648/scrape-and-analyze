# Phase 0 Research: CI/CD-Integrated Data Migration Framework

All open questions from the feature spec were already resolved through an interactive design discussion before this plan was written (see spec.md's Input/Assumptions). This document records the concrete technical decisions needed to implement those already-settled requirements — i.e. "how," given the spec already answered "what."

## 1. Chain/ordering resolution (replaces numeric-filename sort)

**Decision**: Each version-script module gains `down_revision: Optional[str] = None` (the `name` of its predecessor, `None` for the first script). `discover_versions()` is rewritten to:
1. Glob all `*.py` files in `scripts/data/versions/` (excluding `__init__.py`) — no longer filtered to `[0-9]*.py`.
2. Load every module, build a `name -> module` dict.
3. Build a reverse index `down_revision_value -> [names that declare it]` to detect forks in one pass.
4. Validate: exactly one module has `down_revision is None` (the root); every non-root module's `down_revision` exists as a key in the `name -> module` dict; no `down_revision` value is claimed by more than one module (fork); walking from the root via a `name -> next` map visits every module exactly once (catches cycles — a cycle means the walk from root terminates before visiting all modules, or a module is unreachable from root).
5. Return the walk order (root first) as the execution order.

**Rationale**: Mirrors Alembic's own `ScriptDirectory` resolution (a linked list via `down_revision`, not directory sort order) exactly, per the settled design decision. A single up-front validation pass (rather than validating lazily during execution) means a broken chain is reported before anything executes — required by FR-005's "refuse to execute ANY migration in the run if the chain is invalid."

**Alternatives considered**:
- *Keep numeric filename sort, add `down_revision` only as a secondary assertion* — rejected per the explicit design decision to fully replace filename-based ordering (avoids the exact merge-collision hazard — two people picking the same next number — that motivated this change in the first place).
- *Support branching/multiple valid next-migrations (full Alembic branch/merge support)* — rejected as out of scope (spec Assumptions: "a single linear sequence is assumed sufficient").

## 2. Schema-state precondition (real meaning for `alembic_revision`)

**Decision**: Each version-script module's `alembic_revision: Optional[str] = None` names an Alembic schema revision ID. Before executing a script that declares one, the runner:
1. Builds an `alembic.config.Config` pointed at the repo's existing `alembic.ini` / `alembic/` directory (same one `alembic upgrade head` already uses — no new config).
2. Uses `alembic.script.ScriptDirectory.from_config(cfg)` to load the real revision graph.
3. Uses `alembic.runtime.migration.MigrationContext.configure(connection)` (via the same SQLAlchemy connection/session already open) to read the database's actual current revision (`get_current_heads()`).
4. Walks backward from the current head(s) via `ScriptDirectory.get_revision(rev).down_revision`, checking whether the declared `alembic_revision` is encountered before reaching the root (`None`). If found → satisfied (reachable/already-passed); if not found → not satisfied.
5. If not satisfied, the runner raises with a message naming both the declared requirement and the DB's actual current revision, and does not execute the script's `up()`.

**Rationale**: This is a *reachability* check (walk the real history), not an exact-match comparison, per the explicit design decision — a data migration written well after its companion schema change must still run correctly against a DB that has since moved many revisions further. Reusing Alembic's own `ScriptDirectory`/`MigrationContext` (rather than hand-rolling revision-graph parsing) guarantees this check is always consistent with what `alembic upgrade head`/`alembic current` itself would report, with no duplicate source of truth.

**Alternatives considered**:
- *Store/compare a simple version counter instead of Alembic's real revision IDs* — rejected; would require inventing and maintaining a second, parallel versioning scheme when Alembic's own graph already exists and is authoritative.
- *Exact-match the immediately-prior revision only* — rejected per explicit design decision (data migrations aren't tied to one specific schema transition).
- *Persist the checked revision into `data_migrations` as an audit column* — rejected per explicit design decision (precondition-only, no new column).

## 3. Per-script transactional execution with fail-fast

**Decision**: `run_pending()`/`run_one()` wrap each script's `up(session)` call as follows:
```python
try:
    up(session)
except Exception:
    session.rollback()
    log/print the error
    raise SystemExit(1)   # (or equivalent non-zero exit at the CLI boundary)
else:
    session.commit()
    _record_executed(session, name, description)
```
On any exception, the loop over the chain stops immediately (later scripts are not attempted). `_record_executed()` (which does its own `INSERT` + `commit()`) is only reached on the `else` branch, i.e. only after `up()` returns without raising.

**Rationale**: Directly implements FR-009 through FR-012 — no partial writes retained (rollback before any commit), not recorded as applied (record only happens after success), later chained scripts don't run (loop stops), and the process exits non-zero so the containing CI step (and therefore the job) is marked failed. This mirrors Alembic's own per-revision transactional behavior on a transactional DDL database (PostgreSQL).

**Alternatives considered**:
- *Auto-invoke the script's `down()` on failure as cleanup* — rejected per explicit design decision (FR-014: reversal stays a deliberate, human-triggered action only; `down()` may not even be safe/meaningful to run against a script that never fully applied).
- *Continue running remaining scripts in the chain after a failure, reporting failures at the end* — rejected; later scripts may depend on the failed one's effects (that's exactly what the chain expresses), so continuing risks compounding a bad state.

## 4. CI wiring mechanism

**Decision**: Add one explicit step to `ci.yml`'s `migrate` job (immediately after its existing `Run alembic upgrade` step) and one explicit step to `release.yml`'s release job (immediately after its existing `Run alembic upgrade on production DB` step), each running `uv run python scripts/run_data_migrations.py` with the same `DATABASE_URL` env var the preceding alembic step already uses. No `--include-api` flag is passed (matches today's default manual behavior — FR-003).

**Rationale**: Matches this repository's existing convention of small, explicit, separately-named CI steps (e.g. `release.yml` already calls `scripts/release/check_stamped.py`, `generate_release_notes.py`, `extract_release_body.py` as discrete steps) rather than hiding cross-cutting behavior inside an implicit hook. An alternative of hooking this into Alembic's own `env.py` post-upgrade event was explicitly considered and rejected during design: it would silently also fire in the three ephemeral-test-DB jobs (requiring a suppression env var — arguably worse than just not adding a step there) and would entangle data-migration failure semantics with schema-migration failure semantics inside a single Python process, which FR-013 requires to stay independent.

**Alternatives considered**:
- *Alembic `env.py` post-upgrade hook* — rejected (see above; violates FR-002's ephemeral-DB exclusion and blurs FR-013's failure-independence requirement).
- *New dedicated GitHub Actions job* — rejected as unnecessary; the existing `migrate`/release jobs are already the correct scope and already gate the right downstream jobs via `needs:`.
- *Combine both commands into a single shell step (`alembic upgrade head && uv run python scripts/run_data_migrations.py`)* — viable and roughly equivalent; kept as an implementation-time styling choice (two `- name:` steps vs. one step with two commands) rather than a load-bearing design decision, since both produce identical execution order and failure semantics.

## 5. Testing approach

**Decision**: New unit tests under `scripts/tests/test_data_migrations_runner.py`, following the existing mock-based pattern (`unittest.mock.MagicMock` for the SQLAlchemy session, `pytest.MonkeyPatch`/`tmp_path` for constructing fake `scripts/data/versions/`-shaped directories of fixture modules). Covers: chain resolution (linear success case, fork detection, missing-reference detection, cycle detection), precondition-check reachability logic (mocking `ScriptDirectory`/`MigrationContext` rather than requiring a real Postgres + Alembic history in a unit test), and transactional fail-fast behavior (a fixture script whose `up()` raises, asserting rollback + non-recording + chain-stop).

**Rationale**: Matches Constitution Principle III (mandatory test tasks) and this project's established script-testing convention (`scripts/tests/test_backfill_tag_group_definitions.py` already uses exactly this MagicMock-session style with no real DB). No integration test against a real Postgres + Alembic history is required for the unit-level chain/precondition logic; if desired, a lightweight `@pytest.mark.integration` smoke test could later verify the two new CI steps' actual shell invocation end-to-end, but that is not required to satisfy this feature's functional requirements.

**Alternatives considered**:
- *Require a real Alembic-migrated test database for these unit tests* — rejected as unnecessary; the precondition logic only needs `ScriptDirectory`/`MigrationContext`'s return values, which can be mocked/faked without a live database, keeping these tests fast and DB-independent like the rest of `scripts/tests/`.
