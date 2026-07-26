# Phase 1 Data Model: CI/CD-Integrated Data Migration Framework

This feature does not add or change any database table. It changes the *shape* of the Python module interface that `scripts/data/versions/*.py` files must implement, and the in-memory structures the runner builds from them. No `contracts/` directory is included (per plan.md's Project Structure — this is purely internal tooling with no external API); the module interface below **is** the contract, since it's what every future migration author writes against.

## Entity: Data Migration (version script module)

Maps to the spec's "Data Migration (version script)" key entity. One Python module per `scripts/data/versions/*.py` file.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `str` | Yes (existing) | Unique identity, matches the `data_migrations.name` DB column. Unchanged by this feature. |
| `description` | `str` | Yes (existing) | Human-readable summary, stored in `data_migrations.description` on execution. Unchanged. |
| `requires_api` | `bool` | No (existing, default `False`) | Whether `up()` calls an external network/paid/rate-limited API. Unchanged — automatic CI runs always skip `True`. |
| `down_revision` | `Optional[str]` | **New** | The `name` of the migration this one must run after; `None` marks this migration as the chain's root (first to run). Exactly one module in `scripts/data/versions/` may have `down_revision = None`. |
| `alembic_revision` | `Optional[str]` | **Redefined** (existed as `str = ""`, display-only) | The Alembic schema revision ID that must already be applied (at or before the database's current position) before this migration may run. `None`/absent means no schema precondition. Never persisted — checked live against the database's actual current Alembic revision at execution time. |
| `up(session)` | function | Yes (existing) | Applies the migration. Must be idempotent-safe to retry (a failed run is never recorded, so it will be retried). Unchanged signature. |
| `down(session)` | function | No (existing) | Manually-triggered reversal. Never invoked automatically on failure. Unchanged. |

**Validation rules** (enforced by the runner before any migration in a run executes — FR-005):
- Exactly one module has `down_revision is None`.
- Every non-`None` `down_revision` value must equal some other module's `name`.
- No two modules declare the same `down_revision` value (no forks).
- Following `down_revision` links from every module must terminate at the root without revisiting a module (no cycles).

**State transitions**: `pending → applied` (via `up()` succeeding + being recorded) or `pending → pending` (via `up()` raising — nothing recorded, eligible for retry on the next run). A separately-tracked `applied → reversed` transition exists via the manual, human-triggered `down()` path (unchanged from today).

## Entity: Migration Execution Record

Maps to the spec's "Migration Execution Record." This is the existing `data_migrations` table — **no schema change**. Documented here only to clarify how the new fields interact with it:

| Column | Existing/New | Notes |
|---|---|---|
| `name` | Existing | Matches the module's `name`. |
| `description` | Existing | Matches the module's `description` at the time it was executed. |
| `executed_at` | Existing | Set when `up()` succeeds and is recorded. |
| `rolled_back_at` | Existing | Set only by the manual `down()` path (`run_down()`), unchanged. |

`down_revision` and `alembic_revision` are **not** added as columns — both are read from the Python module at runtime and used only as pre-execution logic (ordering and gating respectively), never persisted, per the explicit design decision recorded in spec.md's Assumptions and FR-008.

## Entity: Schema State Reference

Maps to the spec's "Schema State Reference." Not a stored entity — it is the `alembic_revision` string value described above, interpreted at check-time against Alembic's own revision graph (`alembic.script.ScriptDirectory`) and the database's actual current position (`alembic.runtime.migration.MigrationContext`). See research.md §2 for the concrete reachability algorithm.

## In-memory runner structures

- `name -> module` dict: built by `discover_versions()` from every file in `scripts/data/versions/`.
- `down_revision -> [names]` reverse index: built transiently during chain validation to detect forks in a single pass.
- Ordered execution list: the validated, root-first walk order, replacing today's `sorted(glob(...))` result. This is the list `run_pending()` iterates.
