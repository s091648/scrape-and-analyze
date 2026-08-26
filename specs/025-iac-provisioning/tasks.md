---

description: "Task list for Infrastructure as Code for Deployment Environments"
---

# Tasks: Infrastructure as Code for Deployment Environments

**Input**: Design documents from `/specs/025-iac-provisioning/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: This feature has no pytest/Vitest surface (it's Terraform/HCL, not application code — see plan.md's Constitution Check). Per constitution §III, every tasks.md still requires a dedicated test phase; here that means `terraform plan`/`apply`-based verification against real Railway/GitHub resources, checked against each story's Acceptance Scenarios in spec.md, rather than a pytest/Vitest suite.

**Organization**: Tasks are grouped by user story (spec.md priorities: US1 P1, US2 P1, US3 P2, US4 P3) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- File paths are relative to the repository root

## Path Conventions

New top-level `infra/terraform/` directory (per plan.md's Project Structure), plus additions to the existing `Makefile`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, and `CLAUDE.md`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffolding and one-time external bootstrap, before any Terraform resource can be declared.

- [X] T001 Create the `infra/terraform/{modules/railway-service,modules/github-ci-config,environments/staging,environments/production}` directory skeleton per plan.md's Project Structure
- [X] T002 [P] `infra/terraform/versions.tf` — pin `required_providers` (`terraform-community-providers/railway ~> 0.6`, `integrations/github ~> 6.0`, `terraform >= 1.9`) per research.md §2/§3 (adapted: one `versions.tf` per environment, kept identical — Terraform requires a full `terraform {}` block per root module, see each file's header comment)
- [X] T003 [P] `infra/terraform/README.md` — short pointer to `specs/025-iac-provisioning/quickstart.md`, and an explicit note that Railway's managed database services (Redis/Postgres) are out of scope per FR-014
- [X] T004 Perform the one-time external bootstrap per `specs/025-iac-provisioning/quickstart.md` §"One-time bootstrap": create the HCP Terraform org + `scrape-analyzer-staging`/`scrape-analyzer-production` workspaces (**local** execution mode — see research.md §9's execution-mode gotcha), generate `TF_API_TOKEN`/`TF_GITHUB_TOKEN` and verified the existing `RAILWAY_TOKEN` is account-level (all three confirmed working locally via `infra/terraform/.env.local` and the pre-implementation PoC). **Deferred to Phase 5 (T032/T033)**: storing `TF_API_TOKEN`/`TF_GITHUB_TOKEN` as GitHub Actions secrets — not needed until CI actually runs `terraform apply`
- [X] T005 [P] Add `terraform-fmt`, `terraform-validate`, `terraform-plan`, `terraform-apply`, `terraform-drift-check` targets to `Makefile`, each accepting `ENV=staging|production` and wrapping `terraform -chdir=infra/terraform/environments/$(ENV) <cmd>` per plan.md's CI integration decision (research.md §7) — deliberately not run via `docker compose` (see Makefile comment); credentials sourced from `infra/terraform/.env.local`, not the root `.env`

**Checkpoint**: Directory structure exists, bootstrap credentials are in place, `make terraform-*` targets are callable (against an as-yet-empty config).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Per-environment backend/provider wiring that every user story's Terraform code depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 [P] `infra/terraform/environments/staging/backend.tf` — HCP Terraform remote backend block targeting workspace `scrape-analyzer-staging` (data-model.md's Environment entity)
- [X] T007 [P] `infra/terraform/environments/production/backend.tf` — same, targeting workspace `scrape-analyzer-production`
- [X] T008 [P] `infra/terraform/environments/staging/variables.tf` + `terraform.tfvars` — root input variables, including `sensitive = true` declarations for `railway_token`/`github_token` (values supplied only via `TF_VAR_*` at apply time, never literal in `.tfvars`, per FR-004a)
- [X] T009 [P] `infra/terraform/environments/production/variables.tf` + `terraform.tfvars` — same shape for production
- [X] T010 [P] `infra/terraform/environments/staging/main.tf` — configure the `railway` and `github` provider blocks (tokens from T008's variables); **adapted**: no `railway_environment` data source exists in this provider (confirmed during the PoC — it has no data sources at all, research.md §9), so `var.railway_environment_id` is referenced directly as a plain variable instead — depends on T008
- [X] T011 [P] `infra/terraform/environments/production/main.tf` — same for production — depends on T009
- [X] T012 Ran `make terraform-plan ENV=staging` and `make terraform-plan ENV=production` — both connected and authenticated (`No changes. Your infrastructure matches the configuration.`). Found and fixed a real gap along the way: `terraform init` auto-creating `scrape-analyzer-staging` defaulted its execution-mode to `remote` (would have silently broken FR-004a's secret flow); patched to `local` via the Terraform Cloud API, and `scrape-analyzer-production` was created directly with `local` mode — see research.md §9 — depends on T004–T011

**Checkpoint**: Both environments' backends/providers are live and authenticated; ready for real resources.

---

## Phase 3: User Story 1 - Declare deployment infrastructure as version-controlled code (Priority: P1) 🎯 MVP

**Goal**: A reusable `railway-service` module exists and every one of the ten app services is registered + configured declaratively in both environments, matching what's currently on the dashboard, with zero manual dashboard steps.

**Independent Test**: Take one existing service's current dashboard configuration, express it declaratively, apply it against the real Railway project, and confirm the resulting service matches what the dashboard previously showed.

### Tests for User Story 1

- [X] T013 [P] [US1] Verification: ran `make terraform-plan` for **both** `ENV=staging` and `ENV=production` after importing all ten services — both report `No changes. Your infrastructure matches the configuration.` (spec.md US1 Acceptance Scenario 1)
- [X] T014 [P] [US1] Verification: covered by the pre-implementation sandbox PoC (declare → `plan` → `apply` → independently-verified-via-API → `destroy`, fully working end to end) rather than a real change against production, per the maintainer's explicit preference not to apply against production yet — see conversation history and research.md §9. The mechanics this task checks were proven there; the actual "change a real service's variable" exercise happens for real in US2 (T021), scoped to `development` per the maintainer's instruction

### Implementation for User Story 1

**Adapted mid-implementation** (research.md §9, contracts/railway-service-module.md): split into two modules — `railway-service` (registration, production-only) and `railway-variables` (per-environment) — because `railway_service` reads/writes only the project's primary (production) ServiceInstance; declaring it in both environments' state would conflict. `environments/production/main.tf` uses real Railway service names (`weekly report`, `dedup_reconcile`, `storybook UI`, `dashboard-frontend`, `scrape-and-analyze`, `refresh metrics`, `fastembed`, `dashboard-backend`, `chatbot-plugin`, `backfill_rag` — confirmed via the real project's API, several differ from the hyphen-guessed names this task list originally used) and real IDs queried directly.

- [X] T015 [US1] `infra/terraform/modules/railway-service/variables.tf` — `service_name`, `railway_project_id`, `source_repo`, `root_directory` (dropped `railway_environment_id`/`config_path`/`variables` — see adaptation note); `infra/terraform/modules/railway-variables/variables.tf` — `service_id`, `railway_environment_id`, `variables` — per the revised `contracts/railway-service-module.md`
- [X] T016 [US1] `infra/terraform/modules/railway-service/main.tf` — `railway_service` resource only (no `config_path`: confirmed via the real API that all ten services have `railwayConfigFile: null` — build/start stays entirely `railway up`'s local `railway.toml` detection, untouched by Terraform); `infra/terraform/modules/railway-variables/main.tf` — `railway_variable` resources from the `variables` map — depends on T015
- [X] T017 [US1] `infra/terraform/modules/railway-service/outputs.tf` — `railway_service_id`; `infra/terraform/modules/railway-variables/outputs.tf` — `variable_names` — depends on T016
- [X] T018 [US1] `infra/terraform/environments/production/main.tf` — instantiate `module "dashboard_backend"` (`railway-service`, pilot), then `terraform import` `d20f24b5-6c3f-4732-a9b8-de13486db754`. Hit and fixed two real provider issues along the way (research.md §9): `regions` panics with a "Value Conversion Error" on this provider version (`terraform-provider-railway` issues #35/#49) and `source_repo_branch` is required-but-never-readable — both handled via `lifecycle.ignore_changes` rather than fighting them. `railway-variables` deferred to US2 (T023-T028) as planned — depends on T011, T016
- [X] T019 [US1] `infra/terraform/environments/staging/main.tf` — added a `terraform_remote_state` data source reading production's `service_ids` output (confirmed working: `terraform plan` reads it and reports no changes). No `railway-service`/import needed here — that resource only ever exists in production (research.md §9); staging has nothing else to import for *registration* since the same underlying service object is what production already owns. `railway-variables` deferred to US2 — depends on T010, T016, T018
- [X] T020 [US1] Extended production with the remaining nine services (real names/IDs confirmed via the GraphQL API: `weekly report`, `dedup_reconcile`, `storybook UI`, `dashboard-frontend`, `scrape-and-analyze`, `refresh metrics`, `fastembed`, `chatbot-plugin` [own repo, `root_directory = null`], `backfill_rag`) + real production `cron_schedule` values where applicable, all imported. `terraform plan` for **both** `ENV=staging` and `ENV=production` reports `No changes` — FR-001/FR-010/SC-003 satisfied, zero applies against real infrastructure were needed to get there — depends on T018, T019

**Checkpoint**: All ten services are declared and imported in both environments; `terraform plan` shows zero unexpected diff in either workspace. User Story 1 is independently functional.

---

## Phase 4: User Story 2 - Manage environment variables per environment without manual dashboard edits (Priority: P1)

**Goal**: Variable add/update/remove is a one-file-edit-plus-apply workflow, independent per environment, with secrets never touching plaintext files — and the same closed loop extends to the GitHub Actions secrets/variables `ci.yml`/`release.yml` read (FR-012).

**Independent Test**: Add a new non-secret environment variable to the declarative definition for staging, apply it, and confirm the running staging service sees the new value without opening the hosting dashboard.

### Tests for User Story 2

- [ ] T021 [P] [US2] Verification: add a new non-secret variable to one service's staging declaration only, apply, and confirm only the staging service is affected while production is untouched (spec.md US2 Acceptance Scenario 1/3)
- [ ] T022 [P] [US2] Verification: declare a secret variable (value from `TF_VAR_*`), apply, then grep `infra/terraform/**` and review the CI job's log output to confirm the value never appears in plaintext anywhere (spec.md US2 Acceptance Scenario 2, FR-004)

### Implementation for User Story 2

- [ ] T023 [US2] `infra/terraform/modules/github-ci-config/variables.tf` — define `repository`, `github_environment_name`, `secrets` (sensitive map), `variables` per `contracts/github-ci-config-module.md`
- [ ] T024 [US2] `infra/terraform/modules/github-ci-config/main.tf` — `github_actions_secret`/`github_actions_environment_secret` + `github_actions_variable` resources — depends on T023
- [ ] T025 [US2] `infra/terraform/modules/github-ci-config/outputs.tf` — `managed_secret_names`, `managed_variable_names` outputs — depends on T024
- [ ] T026 [US2] `infra/terraform/environments/staging/main.tf` — instantiate `module "github_ci_staging"` scoped to the `scraper / staging` GitHub Environment, declaring the existing `vars.RAILWAY_SERVICE_ID_*` (literal, using T017's `railway_service_id` outputs where possible) and `secrets.RAILWAY_TOKEN`/`DATABASE_URL`/etc. (from `TF_VAR_*`), then `terraform import` each existing GitHub secret/variable — depends on T024, T020
- [ ] T027 [US2] `infra/terraform/environments/production/main.tf` — same for the `scraper / production` GitHub Environment, plus one repo-level (non-environment-scoped) `github-ci-config` instance for secrets/variables that aren't environment-scoped today (`CODECOV_TOKEN`, `GIST_SECRET`, `GIST_ID`, `NPM_TOKEN`, `RELEASE_PAT`) — depends on T024, T020
- [ ] T028 [US2] Define the `TF_VAR_*` environment mapping (which existing GitHub secret feeds which Terraform variable) in a checked-in reference table in `infra/terraform/README.md`, ready for the CI jobs Phase 5 wires up

**Checkpoint**: Every variable — Railway-side and GitHub-side — is declared from one place, per-environment isolation is demonstrated, and no secret value exists in plaintext anywhere in the repo. User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Apply infrastructure changes from the existing CI/CD pipelines (Priority: P2)

**Goal**: `ci.yml`'s PR-time staging flow and `release.yml`'s tag-time production flow apply the declared infrastructure automatically, on the exact triggers `railway up` already uses — never on a bare `master` push (Constitution Principle V).

**Independent Test**: Add an infrastructure change to a PR branch, confirm `ci.yml`'s staging deploy step applies it to the shared staging environment, then confirm a tagged release applies it to production via `release.yml`.

### Tests for User Story 3

- [ ] T029 [P] [US3] Verification: open a PR with a trivial `infra/terraform/**` change, confirm the new PR-gated job posts a `terraform plan` diff, and confirm a later PR's staging deploy job actually applies it (spec.md US3 Acceptance Scenario 1)
- [ ] T030 [P] [US3] Verification: cut a test tag and confirm `release.yml`'s new step applies the change to the `production` workspace (spec.md US3 Acceptance Scenario 2)

### Implementation for User Story 3

- [X] T031 [US3] `.github/workflows/ci.yml` — new job `terraform-plan` (PR-gated) running `terraform fmt -check` / `init` / `validate` / `plan` against the `staging` workspace, folded into `check-lockfile`'s slot rather than path-filtered to `infra/terraform/**` — runs on every PR unconditionally (cheap, ~10-30s, doubles as a lightweight drift check). **Adapted**: uses `hashicorp/setup-terraform@v3` + direct `terraform` calls rather than `make terraform-plan` (Make isn't installed on the `ubuntu-latest` runner by default and installing it isn't worth it for a two-line wrapper CI already inlines)
- [X] T032 [US3] `.github/workflows/ci.yml` — new job `deploy-staging-terraform`, gated on `terraform-plan` succeeding, PR-only. **Discovered a real secret-naming collision while wiring this**: the account-level Railway token Terraform needs cannot reuse the `RAILWAY_TOKEN` secret name — that's already the existing environment-scoped, *project*-level secret `railway up`/`railway down` depend on; overwriting it would break those steps. Introduced a new secret name, `TF_RAILWAY_TOKEN`, exclusively for the Terraform provider (documented in `infra/terraform/README.md`) — depends on T031
- [X] T033 [US3] `.github/workflows/release.yml` — new tag-gated steps (`terraform init`/`apply` against `production`) inserted before the existing Railway deploy step, same `TF_RAILWAY_TOKEN`/`TF_GITHUB_TOKEN`/`TF_API_TOKEN` secrets wiring as T032 — depends on T032
- [ ] T034 [US3] Verification: deliberately break a declaration (e.g. reference an undefined variable), confirm the CI job fails loudly rather than continuing (spec.md US3 Acceptance Scenario 3, FR-006) — then revert the breakage — depends on T032

**Checkpoint**: Infrastructure changes now ship through the same automated, review-gated pipelines as application code. User Stories 1–3 all work independently.

---

## Phase 6: User Story 4 - Detect configuration drift (Priority: P3)

**Goal**: An on-demand check surfaces any out-of-band manual change made directly on the hosting platform or GitHub, instead of letting it silently persist.

**Independent Test**: Manually change one setting directly in the hosting dashboard (bypassing IaC), then run the drift check and confirm it reports that specific setting as changed.

### Tests for User Story 4

- [ ] T035 [P] [US4] Verification: manually change one Railway dashboard setting outside Terraform, run the drift check, and confirm it reports exactly that setting as different — then manually revert it (spec.md US4 Acceptance Scenario 2)

### Implementation for User Story 4

- [ ] T036 [US4] Add a `terraform-drift-check` target to `Makefile` running `terraform plan -detailed-exitcode` per environment, treating exit code `2` as "drift detected" and `0` as "in sync" (exit code `1` remains a hard error) — depends on Phase 2's backend/provider wiring
- [ ] T037 [US4] `.github/workflows/ci.yml` — optional `workflow_dispatch` job running T036's drift check per environment on demand and writing the result to the job summary

**Checkpoint**: All four original user stories are independently functional and demonstrable.

---

## Phase 7: User Story 5 - Centralize application-side environment variable reads (Priority: P2)

**Added mid-implementation** during User Story 2's audit (cross-referencing `backend/config.py`/`src/config/settings.py` against real Railway variables) — see spec.md's Clarifications/Assumptions and FR-015–FR-019. Scope: production code changes across `src/`, `shared/`, and `frontend/` — not Terraform.

**Goal**: Every service reads every environment variable through exactly one designated module, with zero direct `os.environ`/`process.env` calls anywhere else, so the Terraform-side inventory (US2) can't silently drift out of sync with undiscoverable ad-hoc reads again.

**Independent Test**: Repo-wide search for direct environment-variable access outside each service's designated module returns zero results; every affected service's test suite still passes.

### Tests for User Story 5

- [X] T050 [P] [US5] Added `test_get_run_immediately_reflects_live_change_without_reload`/`test_get_grafana_loki_config_reflects_live_change_without_reload` to `src/tests/unit/config/test_config.py`, plus `test_geoip_db_path_reads_env`/`test_geoip_db_path_has_default` to `backend/tests/test_config.py`. Full existing suites (`test_config.py`, `test_main.py`, `test_loki_logging.py`, `test_geoip.py`, `backend/tests/test_config.py`, `test_bootstrap.py`) all re-run and pass — no regressions
- [X] T051 [P] [US5] Added `frontend/tests/unit/env-server.test.ts` + `env-client.test.ts` (Vitest, using `vi.resetModules()` + dynamic import per case). Full frontend suite re-run: **1324/1324 tests, 102/102 files pass**

### Implementation for User Story 5

- [X] T042 [US5] Added `get_run_immediately()` to `src/config/settings.py`; `src/entrypoints/cli/main.py` now calls it instead of reading `os.environ` directly (unused `import os` removed) (spec.md US5 Acceptance Scenario 1)
- [X] T043 [US5] Added `get_grafana_loki_config()` to `src/config/settings.py` (returns `(url, user, key)`); `src/infrastructure/shared/observability/loki_logging.py` now calls it instead of three direct `os.environ.get` calls (spec.md US5 Acceptance Scenario 1)
- [X] T044 [US5] Added `GEOIP_DB_PATH` to `backend/config.py`; `shared/utils/geoip.py` now exposes `configure(db_path)` instead of reading `os.environ` at import time, called once from `backend/main.py`'s module-level startup sequence (spec.md US5 Acceptance Scenario 2, FR-017)
- [X] T045 [P] [US5] Created `frontend/lib/env.server.ts` — raw (no baked-in defaults, matching each call site's own historical fallback) re-exports of every non-`NEXT_PUBLIC_` var this app reads (FR-018)
- [X] T046 [P] [US5] Created `frontend/lib/env.client.ts` — `NEXT_PUBLIC_*` vars plus `APP_ENV`/`SENTRY_DSN` (next.config.ts-whitelisted for client exposure — documented in the file's header, not just NEXT_PUBLIC_-prefixed ones) (FR-018)
- [X] T047 [US5] Migrated all 12 real app-runtime call sites (proxy route, grafana-embed route, link-google start/callback routes, monitoring page, `lib/auth.ts`, `lib/server/ssr-fetch.ts`, `lib/loki-logger.ts`, `instrumentation-client.ts`, `nav-bar.tsx`, both chat providers) to import from `env.server.ts`/`env.client.ts`. Verification grep confirms the only remaining direct `process.env` reads are in explicitly-excluded test/tooling/build-config files (spec.md US5 Acceptance Scenario 3) — depends on T045, T046
- [X] T048 [US5] Added an ESLint `no-restricted-properties` rule forbidding `process.env` access outside `env.server.ts`/`env.client.ts`/config/tooling files (`frontend/eslint.config.mjs`), plus `.github/scripts/check-env-var-centralization.sh` covering both the frontend rule and the Python side (`os.environ` outside each service's `config.py`/`settings.py`, with narrow documented exceptions for the two data-driven `api_key_env` redirects). Wired into CI as an extra step on the existing `check-lockfile` job (renamed "Verify uv.lock & Env Var Centralization") rather than a new standalone job — same enforcement, no extra runner/checkout overhead (FR-019, spec.md US5 Acceptance Scenario 4)
- [X] T049 [US5] Ran `.github/scripts/check-env-var-centralization.sh` locally — passes cleanly across `backend/`, `src/`, `chatbot-plugin/src/`, `fastembed/src/`, `shared/`, and `frontend/` — satisfies SC-007

**Checkpoint**: Application code and the Terraform-side inventory (US2) now describe the same reality, with an automated guard against future drift.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and safety-net checks spanning every story.

- [ ] T038 [P] Update `CLAUDE.md`'s Commands table with the new `make terraform-fmt`/`terraform-validate`/`terraform-plan`/`terraform-apply`/`terraform-drift-check` targets
- [ ] T039 [P] Update `CLAUDE.md`'s Architecture section to list `infra/terraform/` alongside `src/`/`backend/`/`frontend/`/`models/`, one sentence per module's responsibility
- [ ] T040 Re-run every step of `specs/025-iac-provisioning/quickstart.md` end-to-end after all tasks above are complete, and correct the doc wherever reality drifted from what was written during planning
- [ ] T041 [P] Repo-wide grep across `infra/terraform/**/*.tf` and `**/*.tfvars` for anything that looks like a literal secret value, confirming SC-005 ("no secret value appears in plaintext in the repository's version history")

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup (needs T004's bootstrap credentials, T005's Makefile targets) — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational; T026/T027 also depend on US1's T020 (needs all ten services' `railway_service_id` outputs to fully populate `RAILWAY_SERVICE_ID_*` variables) — not independent of US1 in practice, even though both are P1
- **User Story 3 (Phase 5)**: Depends on Foundational; T032 depends on US2's T028 (the `TF_VAR_*` mapping it wires into CI)
- **User Story 4 (Phase 6)**: Depends on Foundational only — genuinely independent of US1–US3, since a drift check works against whatever is already declared, even a minimal subset
- **User Story 5 (Phase 7)**: Independent of Foundational and every other user story — pure application code changes (`src/`, `shared/`, `frontend/`), no Terraform dependency. Can run in parallel with any other phase
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### Within Each User Story

- Module `variables.tf` → `main.tf` → `outputs.tf` (each module)
- Module implementation before any environment root config instantiates it
- `terraform import` immediately follows first instantiation of any pre-existing resource (never plan/apply against an un-imported resource that already exists)
- Verification tasks run after the implementation tasks they check, not "first" as a red/green TDD cycle — there is no code to fail red for a declarative config; the "test" is confirming an apply against real infrastructure matches the Acceptance Scenario

### Parallel Opportunities

- T002, T003 (Setup) — different files
- T006/T007, T008/T009, T010/T011 (Foundational) — staging vs. production are always different files
- T013/T014 (US1 verification) — independent checks
- T021/T022 (US2 verification) — independent checks
- T029/T030 (US3 verification) — independent checks
- T050/T051 (US5 tests), T045/T046 (US5 env.server.ts/env.client.ts) — different files
- T038/T039/T041 (Polish) — different concerns, different files

---

## Parallel Example: Foundational Phase

```bash
# Launch both environments' backend + variable wiring together:
Task: "infra/terraform/environments/staging/backend.tf — HCP Terraform workspace scrape-analyzer-staging"
Task: "infra/terraform/environments/production/backend.tf — HCP Terraform workspace scrape-analyzer-production"
Task: "infra/terraform/environments/staging/variables.tf + terraform.tfvars"
Task: "infra/terraform/environments/production/variables.tf + terraform.tfvars"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks everything)
3. Complete Phase 3: User Story 1 — all ten services declared, `terraform plan` clean
4. **STOP and VALIDATE**: `make terraform-plan ENV=staging` and `ENV=production` both show zero diff; every service's live config still matches what the dashboard showed before migration
5. This alone already delivers the core value: no more manual dashboard clicking to see or change a service's configuration

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. User Story 1 → all services declared and importable → validate → this is the MVP
3. User Story 2 → variable workflow + GitHub secrets/variables closed loop → validate
4. User Story 3 → CI/CD wiring, so changes ship without a manual `terraform apply` → validate
5. User Story 4 → drift detection safety net → validate

Each story adds value without breaking the previous ones; because User Story 4 has no dependency on US2/US3, it can be pulled forward if drift detection turns out to be more urgent than CI wiring.

---

## Notes

- [P] tasks touch different files and have no unmet dependency
- [Story] label maps each task to its spec.md user story for traceability
- Because this feature manages real, already-running production infrastructure, every `terraform apply` task (T018–T020, T026–T027, and anything run via T032/T033) MUST be preceded by reviewing the corresponding `terraform plan` output — never apply blind, even during implementation
- Commit after each task or logical group, per standard project convention
- Stop at any checkpoint to validate a story independently before moving on
- FR-014 (Railway managed database services stay manual) and FR-013 (two standing bootstrap credentials) require no implementation tasks of their own — they are documented constraints (T003, T004) that later tasks must not violate, not features to build
