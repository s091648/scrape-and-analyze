# Feature Specification: CI/CD-Integrated Data Migration Framework

**Feature Branch**: `019-cicd-data-migrations`

**Created**: 2026-07-26

**Status**: Draft

**Input**: User description: "Bring the existing scripts/data/versions data-migration framework (analogous to alembic for one-off/backfill data jobs, tracked in the data_migrations table added by alembic migration 18) up to CI/CD parity with alembic itself, since it is currently a manual-only tool (make data-migrate) never invoked by .github/workflows/ci.yml or release.yml. Decided during design discussion: (1) trigger points are exactly ci.yml's migrate job (staging) and release.yml's release job (production), immediately after the existing alembic upgrade step, deliberately excluding the three ephemeral-per-job test databases; (2) each migration script declares an explicit predecessor reference (like alembic's down_revision) instead of relying on numeric filename ordering; (3) each migration script may declare a minimum required schema state, checked as a reachability precondition (not an exact-transition match) before execution, refused loudly if unmet, and not persisted anywhere; (4) a failing migration's writes are fully rolled back, it is not recorded as executed, no later chained migration runs in that pass, and the pipeline step fails — without reversing an already-successful schema migration in the same run; (5) migrations requiring external API access are always skipped by automatic runs, identical to today's default manual behavior; (6) no new environment toggle, no new CI job, no change to existing manual invocation. The historical arXiv-ID data-cleanup migration that motivated this work is explicitly out of scope — separate follow-on work built on top of this framework."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pending data migrations apply automatically during deploy (Priority: P1)

As a developer merging a change or cutting a release, any pending data migration is applied automatically against the staging or production database right after the schema migration step succeeds — the same way schema migrations already are — so nobody has to remember to separately, manually trigger it.

**Why this priority**: This is the core gap motivating the feature — the framework already exists and already has a documented manual command, but because nothing in the deploy pipeline ever calls it, it goes unused in practice and bugs whose fix belongs in it end up worked around some other way instead.

**Independent Test**: Add a new data migration script to a branch, open a PR, and confirm the staging pipeline applies it automatically (visible in the pipeline log and reflected in the migration bookkeeping) without any manual command being run; repeat for a production release tag.

**Acceptance Scenarios**:

1. **Given** a pending data migration exists when a pull request is opened, **When** the staging deploy pipeline's migration step runs, **Then** the migration executes automatically against the staging database immediately after the schema migration step succeeds, and is recorded as applied.
2. **Given** a pending data migration exists when a release tag is pushed, **When** the production deploy pipeline runs, **Then** the migration executes automatically against the production database immediately after the schema migration step succeeds.
3. **Given** a data migration is marked as requiring external API access, **When** either automatic pipeline runs, **Then** it is skipped automatically, matching today's default manual-invocation behavior (no flag needed to reproduce this).
4. **Given** no data migrations are pending, **When** either automatic pipeline runs, **Then** the step completes successfully as a no-op.

---

### User Story 2 - Migration order is explicit and collision-proof (Priority: P1)

As a developer adding a new data migration, I declare which specific prior migration it comes after, so execution order is guaranteed correct — including when two people add migrations around the same time — instead of depending on everyone coordinating a shared numeric filename prefix.

**Why this priority**: Automating execution of an ordering scheme that can silently collide (two people picking the same next number, or a file simply sorting wrong) would make the automation in User Story 1 actively dangerous rather than helpful. This has to be solid before automatic execution against real environments is acceptable.

**Independent Test**: Author two migration scripts where one explicitly declares the other as its predecessor, using non-alphabetical names; confirm they still execute in the declared dependency order. Then author two scripts that both claim the same predecessor; confirm the run is refused with a clear conflict message instead of an arbitrary pick.

**Acceptance Scenarios**:

1. **Given** migration B declares migration A as its predecessor, **When** pending migrations are discovered, **Then** A executes before B regardless of filename/discovery order.
2. **Given** two migrations both declare the same predecessor, **When** pending migrations are discovered, **Then** the run is refused with an error identifying the conflicting migrations, and nothing executes.
3. **Given** a migration declares a predecessor that does not exist among the known migrations, **When** pending migrations are discovered, **Then** the run is refused with an error identifying the missing reference, and nothing executes.
4. **Given** the declared predecessor references form a cycle, **When** pending migrations are discovered, **Then** the run is refused with an error identifying the cycle, and nothing executes.

---

### User Story 3 - A migration can't run before the schema it needs exists (Priority: P2)

As a developer whose data migration depends on a schema change that may not have reached every environment yet, I declare the minimum schema state it requires, so the framework blocks execution with a clear, specific error instead of failing confusingly partway through (e.g. a raw "column does not exist" error) when the schema isn't ready.

**Why this priority**: This turns a class of confusing mid-execution failures into an clear, actionable pre-execution error. It's protective rather than the primary value driver of the feature, so it ranks below Stories 1 and 2.

**Independent Test**: Author a migration declaring a schema requirement the target database hasn't reached yet; confirm it's refused with a message naming both the required and the actual current schema state, and confirm it runs normally once the database has passed that point (not necessarily immediately after — also confirm it still runs correctly when the database is several schema changes further ahead than the declared requirement).

**Acceptance Scenarios**:

1. **Given** a migration declares a required schema state the database has not yet reached, **When** the runner attempts to execute it, **Then** it refuses with an error naming the required and current schema states, and no partial execution occurs.
2. **Given** a migration declares a required schema state the database has already passed (whether that was the most recent schema change or several changes ago), **When** the runner attempts to execute it, **Then** it proceeds normally.
3. **Given** a migration declares no schema requirement at all, **When** the runner attempts to execute it, **Then** this precondition check is simply skipped and execution proceeds based on migration ordering alone.

---

### User Story 4 - A failed migration can't corrupt state or take down unrelated work (Priority: P1)

As a developer, when a data migration fails partway through during an automatic deploy run, its database changes are completely undone, it is not falsely marked as completed, no later migration that depends on it is attempted in that same run, and the deploy pipeline clearly reports failure — but a schema migration that already succeeded earlier in the same run is left in place, since it worked correctly and the failure is unrelated to it.

**Why this priority**: This is the safety property that makes automating execution against staging/production (User Story 1) acceptable at all. Without it, turning a previously manual, human-reviewed action into an automatic one would be a net increase in risk rather than a convenience.

**Independent Test**: Introduce a migration that deliberately fails partway through its work; run it through the automatic pipeline; confirm none of its writes persisted, it isn't recorded as applied, any migration chained after it does not run in that pass, the pipeline step is reported as failed and blocks whatever depends on it, and a schema migration that succeeded earlier in the same run remains applied.

**Acceptance Scenarios**:

1. **Given** a migration's execution raises partway through, **When** it runs via the automatic pipeline, **Then** none of its database writes are retained.
2. **Given** a migration fails, **When** the runner's bookkeeping is checked afterward, **Then** the failed migration is not recorded as applied.
3. **Given** a migration fails and other migrations are chained after it, **When** the runner continues, **Then** none of those later migrations are attempted in that same run.
4. **Given** a migration fails during an automatic run, **When** the pipeline evaluates the result, **Then** the deploy step is reported as failed, and any deployment action that depends on that step does not proceed.
5. **Given** a schema migration succeeded earlier in the same pipeline run and a subsequent, unrelated data migration then fails, **When** the pipeline handles the failure, **Then** the already-applied schema migration is not automatically reversed.
6. **Given** a migration previously failed and was never recorded as applied, **When** the pipeline runs again after the underlying problem is fixed, **Then** the migration is attempted again (it was never treated as done).

---

### Edge Cases

- What happens when a locally-executable migration and an API-dependent migration are both pending in the same automatic run? The local one applies; the API-dependent one is skipped; neither blocks the other.
- What happens when the dependency-order validation itself fails (a fork, a missing reference, or a cycle) before anything has executed? The whole run must be refused up front with the specific problem identified — no migration in that batch should partially execute while the ordering problem goes undetected.
- What happens when a migration already recorded as applied in an earlier run appears again in a later run's discovery? It must not execute a second time.
- What happens when someone manually reverses a previously-applied migration (a deliberate, human-triggered action) and the pipeline runs again afterward? It should be treated as pending again and re-applied.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST automatically execute pending data migrations, with no manual step required, as part of exactly two deployment pipelines: the staging deploy pipeline (triggered by a pull request) and the production release pipeline (triggered by a release), immediately after each pipeline's existing schema-migration step succeeds.
- **FR-002**: The system MUST NOT automatically execute data migrations as part of any pipeline path that runs against a disposable, per-run database rather than a persistent staging/production database.
- **FR-003**: Automatic execution MUST skip any data migration flagged as requiring external API access, in both the staging and production pipelines, matching the behavior of today's default manual invocation (no additional configuration required to reproduce this skip).
- **FR-004**: Each data migration MUST declare an explicit reference to the one specific prior migration it depends on, or explicitly declare that it has no predecessor (i.e., it is first). Execution order MUST follow this declared dependency chain, not filename or filesystem discovery order.
- **FR-005**: Before executing any migration in a run, the system MUST validate that the full set of declared predecessor references forms exactly one linear, unbroken sequence: exactly one migration with no predecessor, no two migrations declaring the same predecessor, no reference to a nonexistent migration, and no circular reference. If this validation fails, the system MUST refuse to execute any migration in that run and report the specific problem (which migrations/references are involved).
- **FR-006**: Each data migration MAY declare a minimum required schema state (a specific, already-defined point in the separate schema-migration history) that must already be applied before it can run.
- **FR-007**: Before executing a migration that declares a required schema state, the system MUST verify the target database has actually reached that state or a later one (not merely "at some point," but currently true along the real schema history), and MUST refuse to execute the migration — reporting both the required and current schema state — if this is not satisfied.
- **FR-008**: The declared schema-state requirement (FR-006/FR-007) MUST function purely as a pre-execution check; the system MUST NOT persist a record of what schema state was current at the time a migration executed.
- **FR-009**: Each migration's data-changing work MUST execute as an isolated unit such that if it fails partway through, none of its database writes remain — the database is left exactly as it was before that migration began.
- **FR-010**: A migration that fails MUST NOT be recorded as successfully applied.
- **FR-011**: If a migration fails, the system MUST NOT attempt any migration declared to come after it in the dependency chain during that same run.
- **FR-012**: If a migration fails during an automatic run, the deployment pipeline step MUST report failure such that any subsequent deployment action gated on that step does not proceed.
- **FR-013**: A migration's failure during an automatic run MUST NOT cause an already-successfully-applied schema migration from the same pipeline run to be automatically reversed.
- **FR-014**: Reversing a previously-and-successfully-applied migration MUST remain an explicit, human-triggered action; the system MUST NOT invoke this automatically under any failure condition.
- **FR-015**: Existing manual invocation of the data migration framework MUST continue to work unchanged for local/manual use, independent of the automatic pipeline integration.
- **FR-016**: The one data migration that exists prior to this feature MUST be updated to explicitly declare that it has no predecessor (it is first in the chain), preserving its current applied/pending status.

### Key Entities

- **Data Migration (version script)**: A unit of standalone, one-off data work — identified by a unique name, with a human-readable description, a flag for whether it requires external API access, a declared reference to its predecessor (or none), an optional declared minimum required schema state, an apply action, and an optional, separately-and-manually-triggered reverse action.
- **Migration Execution Record**: The durable record of which data migrations have been successfully applied (and, where applicable, manually reversed), used to determine what remains pending for a given run.
- **Schema State Reference**: A pointer to a specific, already-defined point in the separate schema-migration history, used only as a pre-execution precondition for a data migration — not stored as part of the execution record.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of staging deploys and production releases that include a pending, non-API data migration apply it automatically with zero manual steps, measured across deploys after this feature ships.
- **SC-002**: Zero observed instances, across all pipeline runs, of a data migration executing out of its declared dependency order.
- **SC-003**: Zero observed instances of a failed migration leaving retained database writes or being incorrectly recorded as applied.
- **SC-004**: 100% of migration failures during automatic runs result in the deploy pipeline reporting failure and halting dependent steps, verified across intentionally-triggered failure scenarios.
- **SC-005**: Zero observed instances of an unrelated, successfully-applied schema migration being reversed because a data migration failed in the same run.
- **SC-006**: A developer adding a new data migration can determine the required metadata (its predecessor, and, if applicable, its schema requirement) using only an existing migration as a reference, without asking a maintainer, in under 5 minutes.

## Assumptions

- This feature changes only the data-migration framework and its two deployment-pipeline trigger points; it does not change how schema migrations themselves are authored, executed, or reversed.
- "Automatic execution" is scoped to exactly the staging (pull-request-triggered) and production (release-triggered) pipelines that operate against real, persistent databases. Pipeline paths that use a disposable database recreated on every run are explicitly out of scope for automatic execution, since there is no persistent data for a one-off backfill/cleanup migration to act on there.
- Data migrations requiring external API access remain a manually-triggered category regardless of this feature; automating their execution is explicitly out of scope.
- The specific historical data-cleanup migration that motivated this work (an arXiv-identifier normalization fix) is out of scope for this feature — it is separate, follow-on work that will be built on top of the framework delivered here.
- Data changes that are directly caused by and bundled with a schema change continue to belong inside that schema migration's own apply/reverse actions, not this framework — this feature does not change that boundary.
- Branching or merging dependency graphs (more than one valid "next" migration from a given point) are out of scope; a single linear sequence is assumed sufficient for this project's needs.
- No new configuration toggle (environment variable or otherwise) is introduced to enable or suppress automatic execution — the two designated pipelines run it unconditionally, and no other pipeline path does.
