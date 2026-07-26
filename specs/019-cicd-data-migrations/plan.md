# Implementation Plan: CI/CD-Integrated Data Migration Framework

**Branch**: `019-cicd-data-migrations` | **Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/019-cicd-data-migrations/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

`scripts/data/versions/` + `scripts/data/runner.py` is an existing, alembic-analogous framework for one-off/standalone data-quality fixes (tracked in the `data_migrations` table from alembic migration 18), but it has never been wired into CI/CD — it's a manual-only tool (`make data-migrate`). This feature brings it to CI/CD parity with alembic itself: (1) two small, explicit steps added to `ci.yml`'s `migrate` job and `release.yml`'s release job, immediately after the existing `alembic upgrade head` step; (2) the runner's discovery/ordering logic replaced with an alembic-style linked chain (`down_revision` on each version script) instead of numeric-filename sorting; (3) the existing, currently-decorative `alembic_revision` attribute becomes a real, enforced precondition — a reachability check against the DB's actual current alembic revision, refused loudly (not silently skipped) if unmet; (4) each script's `up()` runs inside an explicit DB transaction with fail-fast semantics matching alembic's own failure behavior (roll back, don't record, stop the chain, fail the CI step) while never touching the separate schema-migration's own success/rollback state.

## Technical Context

**Language/Version**: Python 3.11 (matches the rest of `scripts/`, `src/`, `backend/`)

**Primary Dependencies**: SQLAlchemy (session/transaction control — already used by `scripts/data/runner.py`), Alembic's own introspection API (`alembic.script.ScriptDirectory`, `alembic.runtime.migration.MigrationContext`) to read the real schema-revision graph and the DB's current position — no new third-party dependency

**Storage**: PostgreSQL — reads/writes the existing `data_migrations` table (no schema change to it) and reads (read-only) the existing `alembic_version` table via Alembic's own APIs

**Testing**: pytest, mock-based (`unittest.mock.MagicMock` session, following the existing pattern in `scripts/tests/test_backfill_tag_group_definitions.py`) — no real DB required for chain-resolution or precondition-check unit tests; `uv run pytest scripts/tests/`

**Target Platform**: Linux (GitHub Actions `ubuntu-latest` runners for the two new CI steps; Railway Linux containers / local Docker `job_service` for existing manual invocation — unchanged)

**Project Type**: Single-project internal tooling (CLI script + CI workflow steps) inside the existing monorepo — not a new service, no new deployable

**Performance Goals**: N/A — not a latency-sensitive path; the only timing constraint is fitting inside `ci.yml`'s `migrate` job's existing 10-minute job timeout, shared with the `alembic upgrade head` step it follows

**Constraints**: Automatic (CI-triggered) runs MUST NOT perform any external network/API calls (enforced by the existing `requires_api` gate, unchanged); the two new CI steps MUST be plain `uv run python scripts/run_data_migrations.py` invocations — no Makefile/Docker available in GitHub Actions runners for this path (unlike local dev, which keeps using `make data-migrate` unchanged)

**Scale/Scope**: Small — one existing version script (`001_backfill_tag_group_definitions.py`) to update, the runner's internal logic (`scripts/data/runner.py`), and two `.github/workflows/*.yml` files touched. The follow-on arXiv-ID backfill script is explicitly out of scope for this feature.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle III (Test Discipline)** — applies. New/changed logic in `scripts/data/runner.py` (chain resolution, precondition check, transactional execution) MUST ship with pytest coverage under `scripts/tests/`, matching this project's existing script-test convention. No DB-dependent (`@pytest.mark.integration`) tests are strictly required since the new logic is unit-testable with a mocked session, but nothing here removes the option. **PASS.**
- **Principle IV (Docker-First Local Development / Makefile as interface)** — the two new CI steps deliberately do **not** go through Docker/Makefile (GitHub Actions runners don't have this project's `docker compose` stack for this path). This mirrors the *existing* precedent already set by `ci.yml`'s own `Run alembic upgrade` step, which likewise calls `uv run alembic upgrade head` directly rather than `make migrate` — i.e., CI has never followed the Docker-first rule for migrations, because that rule governs local developer workflow, not CI runners. Local/manual invocation (`make data-migrate`) is explicitly unchanged (FR-015). **PASS — not a violation; consistent with existing, already-accepted CI behavior for the sibling `alembic upgrade head` step.**
- **Principle V (Explicit CI/CD Deployment Boundary)** — applies directly, since this feature edits `ci.yml` and `release.yml`. The new steps are added *inside* the two already-gated jobs (`migrate` in `ci.yml`, the release job in `release.yml`) at the same trigger points (`pull_request` for staging, `v*` tag push for production) — no new trigger, no new deploy path, no bypass of the existing PR-review/tag-release gates. A migration failure causes the containing job to fail, which (per FR-012/FR-013 and the constitution's existing "Migration safety" bullet) already correctly cascades to block downstream deploy steps without touching the separate schema-migration rollback path. **PASS.**
- **Governance (amendment note)** — the constitution's Principle V "Migration safety" bullet currently documents only alembic's CI behavior ("On push to master, CI runs `alembic upgrade head`... `rollback` job runs `alembic downgrade -1`"). Once this feature is implemented, that bullet should be extended with a corresponding one-line description of the new data-migration step, per the Governance section's amendment requirement. **Tracked as a task, not a gate failure** — the constitution amendment is a documentation follow-up, not a blocking precondition for this feature's design.

No violations requiring justification — Complexity Tracking table is empty/omitted.

## Project Structure

### Documentation (this feature)

```text
specs/019-cicd-data-migrations/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No `contracts/` directory — this feature has no external API/interface; its only "interface" is the internal version-script module contract, which is documented in `data-model.md` instead (per plan template guidance to skip `contracts/` for purely internal tooling).

### Source Code (repository root)

```text
scripts/
├── run_data_migrations.py          # CLI entrypoint — unchanged interface (--list/--name/--down/--include-api)
├── data/
│   ├── runner.py                   # MODIFIED: chain-based discovery, precondition check, transactional execution
│   └── versions/
│       └── 001_backfill_tag_group_definitions.py   # MODIFIED: add down_revision = None
└── tests/
    └── test_data_migrations_runner.py              # NEW: unit tests for runner.py's new logic

.github/workflows/
├── ci.yml           # MODIFIED: one new step in the `migrate` job, after `Run alembic upgrade`
└── release.yml      # MODIFIED: one new step in the `release` job, after `Run alembic upgrade on production DB`
```

**Structure Decision**: This feature is confined entirely to the existing `scripts/data/` tooling package and two existing CI workflow files — no new top-level directory, no new service, no changes to `src/`, `backend/`, `frontend/`, or `models/`. The `scripts/tests/` convention (flat pytest files, no subpackage) is followed for the new test file rather than introducing a nested test package under `scripts/data/`.

## Complexity Tracking

*No violations — table intentionally omitted.*
