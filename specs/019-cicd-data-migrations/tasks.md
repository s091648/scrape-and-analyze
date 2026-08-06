---

description: "Task list template for feature implementation"
---

# Tasks: CI/CD-Integrated Data Migration Framework

**Input**: Design documents from `/specs/019-cicd-data-migrations/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Tests**: Every tasks.md MUST include at least one dedicated test phase (project constitution §III — tests are NOT optional here regardless of what the spec says). Per this project's established convention (`scripts/tests/test_backfill_tag_group_definitions.py`), all new tests are mock-based pytest (`unittest.mock.MagicMock` session, no real database) under `scripts/tests/`.

**Task ordering note**: Implementation tasks are listed before their corresponding test tasks within each story (matching this project's preferred workflow: implement directly, verify with tests immediately after — not red/green TDD). This does not weaken the test requirement; every story still ships with dedicated coverage before its checkpoint.

**Organization**: Tasks are grouped by user story from spec.md. **Build order deviates from spec.md's story numbering** — see "Why build order differs from story numbering" below.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Why build order differs from story numbering

spec.md lists stories in order of user-facing value (US1 "automatic execution" first). But US1 is only *safe* to turn on once the ordering guarantee (US2) and the fail-fast safety net (US4) exist — enabling automatic execution against real staging/production databases before those exist would be exactly the risk the design discussion identified. So implementation proceeds **US2 → US4 → US3 → US1**: the two P1 runner-safety stories first, then the P2 protective precondition, then the P1 CI-wiring story that depends on all three. This was already anticipated in plan.md's Constitution Check and research.md.

## Path Conventions

Single project (internal tooling within the existing monorepo) — `scripts/data/runner.py`, `scripts/data/versions/`, `scripts/tests/`, `.github/workflows/`. No `frontend/`/`backend/`/`src/` changes.

---

## Phase 1: Setup

**Purpose**: Scaffold the new test file all later phases append to.

- [X] T001 Create `scripts/tests/test_data_migrations_runner.py` with a module docstring, the standard imports (`pytest`, `unittest.mock.MagicMock`), and a small helper for constructing fake version-script modules in-memory (e.g. via `types.ModuleType`, setting `name`/`down_revision`/`alembic_revision`/`requires_api`/`up`/`down` attributes) so later test tasks don't each re-derive this fixture pattern

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the version-script interface fields every story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Document the version-script module interface at the top of `scripts/data/runner.py`: add `down_revision: Optional[str] = None` (predecessor reference; `None` = chain root) and redefine the existing `alembic_revision` field's docstring to state its new meaning ("minimum required Alembic schema revision, checked as a reachability precondition — not a stored audit field") per data-model.md
- [X] T003 Update `scripts/data/versions/001_backfill_tag_group_definitions.py` to add `down_revision = None`, per FR-016 — confirm its existing `alembic_revision = "17_add_vector_failed_task_and_auto_tag"` value is left unchanged

**Checkpoint**: Version-script interface finalized — all four user stories can now build on it.

---

## Phase 3: User Story 2 - Migration order is explicit and collision-proof (Priority: P1)

**Goal**: Replace numeric-filename-prefix ordering with an Alembic-style linked chain (`down_revision`), validated for exactly one root, no forks, no cycles, before anything executes.

**Independent Test**: Author two fixture migration scripts where one declares the other as predecessor using non-alphabetical names; confirm they execute in declared order. Author two scripts claiming the same predecessor; confirm the run is refused with a specific conflict error. No CI, transaction, or schema-precondition logic is needed to verify this story.

### Implementation for User Story 2

- [X] T004 [US2] Rewrite `discover_versions()` in `scripts/data/runner.py` to glob all `*.py` files in `scripts/data/versions/` (excluding `__init__.py`) instead of `sorted(VERSIONS_DIR.glob("[0-9]*.py"))`, loading each into a `name -> module` dict
- [X] T005 [US2] Add a new `_resolve_chain(modules: dict) -> list` function in `scripts/data/runner.py` that validates: exactly one module has `down_revision is None`; every non-`None` `down_revision` value matches some module's `name`; no two modules declare the same `down_revision` (fork detection via a reverse index); walking from the root visits every module exactly once (cycle/unreachable detection) — raising a specific, descriptive error (naming the offending migration name(s)) on any violation
- [X] T006 [US2] Implement the root-first chain walk in `_resolve_chain()` that returns the validated execution order (list of `(name, module)` in dependency order)
- [X] T007 [US2] Update `run_pending()`, `run_one()`, and `list_status()` in `scripts/data/runner.py` to consume `_resolve_chain()`'s ordered output instead of the old filename-sorted list from `discover_versions()`

### Tests for User Story 2

- [X] T008 [P] [US2] Unit test in `scripts/tests/test_data_migrations_runner.py`: three fixture scripts declared with non-alphabetical names and an explicit predecessor chain execute/list in the declared dependency order
- [X] T009 [P] [US2] Unit test in `scripts/tests/test_data_migrations_runner.py`: two fixture scripts both declaring the same `down_revision` cause `_resolve_chain()` to raise, identifying both conflicting names, with nothing executed
- [X] T010 [P] [US2] Unit test in `scripts/tests/test_data_migrations_runner.py`: a fixture script's `down_revision` referencing a nonexistent name causes `_resolve_chain()` to raise, identifying the missing reference
- [X] T011 [P] [US2] Unit test in `scripts/tests/test_data_migrations_runner.py`: a fixture chain containing a cycle (A→B→A) causes `_resolve_chain()` to raise, identifying the cycle, with nothing executed

**Checkpoint**: Chain-based ordering is fully functional and independently tested.

---

## Phase 4: User Story 4 - A failed migration can't corrupt state or take down unrelated work (Priority: P1)

**Depends on**: Phase 3 (US2) — needs the chain-ordered execution list to know what "later in the chain" means when stopping after a failure.

**Goal**: Wrap each script's `up()` in transactional, fail-fast execution matching Alembic's own failure behavior, without ever touching schema-migration state.

**Independent Test**: Introduce a fixture script whose `up()` raises partway through; run it via `run_pending()`; confirm no commit occurred, it's not recorded as executed, later chained scripts are skipped, and the process would exit non-zero — all verifiable by calling the runner functions directly, no CI wiring required yet.

### Implementation for User Story 4

- [X] T012 [US4] In `run_pending()`/`run_one()` (`scripts/data/runner.py`), wrap each script's `mod.up(session)` call in a try/except: on exception call `session.rollback()`, log/print the error, and do not call `_record_executed()`; only call `_record_executed()` (which commits) in the success path
- [X] T013 [US4] In `run_pending()`/`run_one()`, stop iterating the chain-ordered list immediately after a failure (no further scripts in that run's remaining chain are attempted)
- [X] T014 [US4] Update `scripts/run_data_migrations.py`'s `main()` (verified: no code change needed — `sys.exit(1)` calls added inside `run_pending()`/`run_one()` already propagate through `main()`'s unguarded call + `finally: session.close()`) to exit with a non-zero status (`sys.exit(1)`) when the runner reports a migration failure, so the containing CI step fails

### Tests for User Story 4

- [X] T015 [P] [US4] Unit test in `scripts/tests/test_data_migrations_runner.py`: a fixture script's `up()` raising results in `session.rollback()` being called and `session.commit()` never being called for that script
- [X] T016 [P] [US4] Unit test in `scripts/tests/test_data_migrations_runner.py`: a failed fixture script does not appear in `get_executed()` afterward (not recorded)
- [X] T017 [P] [US4] Unit test in `scripts/tests/test_data_migrations_runner.py`: when a chain-earlier script fails, a chain-later script's `up()` is never called during that run
- [X] T018 [P] [US4] Unit test in `scripts/tests/test_data_migrations_runner.py`: `scripts/run_data_migrations.py`'s `main()` raises `SystemExit` with a non-zero code when a migration fails
- [X] T019 [US4] Unit test in `scripts/tests/test_data_migrations_runner.py`: asserting the failure-handling code path never calls any Alembic upgrade/downgrade API — confirming a data-migration failure cannot reach into/reverse schema-migration state

**Checkpoint**: Fail-fast/rollback safety is fully functional and independently tested.

---

## Phase 5: User Story 3 - A migration can't run before the schema it needs exists (Priority: P2)

**Depends on**: Phase 2 (Foundational) for the `alembic_revision` field; touches the same `run_pending()`/`run_one()` call sites as Phase 4, so is sequenced after it.

**Goal**: Make the `alembic_revision` field a real, enforced reachability precondition instead of a display-only string.

**Independent Test**: Author a fixture script declaring an `alembic_revision` the (mocked) database hasn't reached; confirm execution is refused with an error naming both the required and current revision. Confirm it runs normally once the (mocked) database has passed that revision, including when several revisions further ahead than the declared one.

### Implementation for User Story 3

- [X] T020 [US3] Add `_alembic_revision_satisfied(connection, required_revision: str) -> bool` in `scripts/data/runner.py`, using `alembic.config.Config` (pointed at the repo's existing `alembic.ini`), `alembic.script.ScriptDirectory.from_config()`, and `alembic.runtime.migration.MigrationContext.configure(connection)` to walk backward from the database's current head(s) via `down_revision` links, returning whether `required_revision` is reached or passed
- [X] T021 [US3] In `run_pending()`/`run_one()`, call `_alembic_revision_satisfied()` before executing any script with a non-`None` `alembic_revision`; on `False`, raise an error naming both the required and the database's actual current revision, and do not call `up()`
- [X] T022 [US3] Confirm scripts with `alembic_revision = None` skip this check entirely and execute based on chain ordering alone (no code change expected beyond an explicit `if mod.alembic_revision is not None:` guard)

### Tests for User Story 3

- [X] T023 [P] [US3] Unit test in `scripts/tests/test_data_migrations_runner.py`: a fixture script requiring a schema revision the mocked `ScriptDirectory`/`MigrationContext` reports as not-yet-reached is refused, with the error naming both revisions
- [X] T024 [P] [US3] Unit test in `scripts/tests/test_data_migrations_runner.py`: a fixture script requiring a schema revision the mocked database has already passed (including a case several revisions further ahead, not just the immediately prior one) executes normally
- [X] T025 [P] [US3] Unit test in `scripts/tests/test_data_migrations_runner.py`: a fixture script with `alembic_revision = None` executes without any call to `_alembic_revision_satisfied()`

**Checkpoint**: Schema-state precondition gate is fully functional and independently tested.

---

## Phase 6: User Story 1 - Pending data migrations apply automatically during deploy (Priority: P1)

**Depends on**: Phase 3 (US2), Phase 4 (US4), and Phase 5 (US3) — per the design discussion, automatic execution against real staging/production databases should not be enabled before ordering correctness, fail-fast safety, and the schema precondition gate all exist.

**Goal**: Wire the now-safe runner into `ci.yml` and `release.yml` so pending migrations apply with zero manual steps.

**Independent Test**: Add a pending fixture/real migration on a branch, open a PR, confirm the staging pipeline's `migrate` job applies it automatically right after `alembic upgrade head`; confirm the same for a production release tag.

### Implementation for User Story 1

- [X] T026 [US1] Add a new step to the `migrate` job in `.github/workflows/ci.yml`, immediately after the existing `Run alembic upgrade` step: `uv run python scripts/run_data_migrations.py`, reusing that step's existing `DATABASE_URL` secret
- [X] T027 [US1] Add a new step to the release job in `.github/workflows/release.yml`, immediately after the existing `Run alembic upgrade on production DB` step: `uv run python scripts/run_data_migrations.py`, reusing that step's existing `DATABASE_URL` secret
- [X] T028 [US1] Verify by inspection that neither new CI step passes `--include-api`, so `requires_api=True` scripts remain skipped automatically in both pipelines (FR-003) — no code change expected, this is a review/confirmation task

### Tests for User Story 1

- [X] T029 [US1] Unit test in `scripts/tests/test_data_migrations_runner.py`: `run_pending(include_api=False)` (the default, matching what the new CI steps invoke) skips a fixture script with `requires_api=True` without calling its `up()`
- [X] T030 [US1] Unit test in `scripts/tests/test_data_migrations_runner.py`: `run_pending()` completes successfully as a no-op when there are zero pending migrations

**Checkpoint**: Automatic CI/CD execution is fully wired, gated correctly, and independently tested. All four user stories are now complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T031 [P] Run through `specs/019-cicd-data-migrations/quickstart.md` locally (`make data-migrate-list`, `make data-migrate`) against a local dev database to confirm the updated `001_backfill_tag_group_definitions.py` and CLI output are unaffected by the runner rewrite
- [X] T032 Amend `.specify/memory/constitution.md`'s Principle V "Migration safety" bullet to document the new automatic data-migration CI/CD step alongside the existing Alembic description, and bump the constitution version per its Governance section
- [X] T033 [P] Run the full new suite: `uv run pytest scripts/tests/test_data_migrations_runner.py -v` and confirm all tests pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **US2 (Phase 3)**: Depends on Foundational only.
- **US4 (Phase 4)**: Depends on Foundational **and** US2 (needs the chain-ordered list).
- **US3 (Phase 5)**: Depends on Foundational; touches the same call sites as US4, so built after it.
- **US1 (Phase 6)**: Depends on US2, US4, **and** US3 — see "Why build order differs from story numbering" above.
- **Polish (Phase 7)**: Depends on all four user stories being complete.

### Parallel Opportunities

- All test tasks marked `[P]` within a story phase can run in parallel (they add independent test functions to the same file, but are logically independent of each other).
- T002 and T003 (Foundational) touch different files and can run in parallel.
- No user story phase can start in parallel with another in this feature — the dependency chain above (US2 → US4 → US3 → US1) is strictly sequential, unlike a typical feature where stories are independent. This is a direct consequence of the safety-first design decision recorded in plan.md and research.md.

---

## Parallel Example: User Story 2

```bash
# After T004-T007 (implementation) land, launch all US2 tests together:
Task: "Unit test: declared-order execution regardless of filename, in scripts/tests/test_data_migrations_runner.py"
Task: "Unit test: fork detection, in scripts/tests/test_data_migrations_runner.py"
Task: "Unit test: missing-predecessor detection, in scripts/tests/test_data_migrations_runner.py"
Task: "Unit test: cycle detection, in scripts/tests/test_data_migrations_runner.py"
```

---

## Implementation Strategy

### This feature does not have an "MVP = just User Story 1" shortcut

Unlike a typical feature where each user story is independently deployable, **US1 (automatic CI/CD execution) is only safe to ship once US2, US4, and US3 all exist** — enabling automatic execution against real staging/production databases without the ordering guarantee and fail-fast safety net would be a net increase in risk, per the design discussion this spec was built from. The practical "smallest deployable slice" for this feature is therefore **Phases 1–6 together** (all four stories) — there is no meaningful partial-deploy checkpoint before that.

That said, each phase is still independently *testable* (per each story's Independent Test in spec.md) as work progresses — you can verify US2's chain logic, then US4's fail-fast logic, then US3's precondition logic, all without touching `ci.yml`/`release.yml`, before finally wiring US1 in as the last, thin integration step.

### Incremental Delivery (testing checkpoints, not deploy checkpoints)

1. Complete Setup + Foundational → interface finalized.
2. Add US2 → verify chain resolution independently (no CI/DB needed).
3. Add US4 → verify fail-fast/rollback independently.
4. Add US3 → verify schema-precondition gate independently.
5. Add US1 → wire into `ci.yml`/`release.yml` — this is the first point at which anything actually deploys differently.
6. Polish.

---

## Notes

- `[P]` tasks touch different files, or add independent test functions to the same file with no shared mutable state.
- `[Story]` label maps each task to its spec.md user story for traceability, even though build order is not story-numeric order (see explanation above).
- Every story ships with dedicated test coverage before its checkpoint, per project constitution §III — this was not made optional despite the generic task-template default.
- Avoid: starting Phase 6 (US1) work before Phases 3–5 are complete and their tests pass — this is the one hard ordering rule this feature relies on for safety.
