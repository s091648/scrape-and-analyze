---

description: "Task list template for feature implementation"
---

# Tasks: Lighthouse Performance Check

**Input**: Design documents from `specs/022-lighthouse-performance-check/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Every tasks.md MUST include at least one dedicated test phase. Tests are NOT optional — omitting test tasks violates the project constitution (§III). This project does not follow TDD (tests are written alongside/after implementation, not test-first) — test tasks below are listed after the implementation tasks they cover, within each story.

**Organization**: Tasks are grouped by user story (spec.md P1/P2/P3) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

This is the existing `backend/` + `frontend/` web-app layout (see plan.md Project Structure). All new files for this feature live under `frontend/` — no backend code changes are needed (the existing `POST /auth/guest` endpoint is reused as-is).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Get the new dependency and ignore-rule in place before any script code is written.

- [X] T001 Add `lighthouse` to `devDependencies` in `frontend/package.json`, installed via `docker compose run --rm frontend npm install` (per project convention: npm install must run inside the frontend Docker container so `frontend/package-lock.json` stays in sync with the Dockerfile's `npm ci`)
- [X] T002 [P] Add `lighthouse-reports/` to `.gitignore` (repo root), mirroring the existing `db_dumps/` entry for generated, non-committed output

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The pieces every user story's flow is built from — Chrome resolution, single-route execution, metric extraction, guest auth, and CLI parsing. None of this is independently user-facing yet.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Create `frontend/scripts/lib/lighthouse-report.mjs` and implement `extractRouteMetrics(lhrJson)`, mapping a parsed Lighthouse JSON ("LHR") result to `{ performanceScore, lcpMs, tbtMs, cls }` per data-model.md `RouteMetrics` (`categories.performance.score * 100` rounded; `audits['largest-contentful-paint'|'total-blocking-time'|'cumulative-layout-shift'].numericValue`)
- [X] T004 Create `frontend/scripts/lighthouse-check.mjs` and implement Chrome-binary resolution (`require('playwright').chromium.executablePath()`) plus a single-route runner that shells out to `npx lighthouse <url> --output=json --output-path=<file> --chrome-flags="--headless=new --no-sandbox --disable-gpu" --extra-headers=<json> --only-categories=performance --quiet` via `child_process`, returning `{ status: "success"|"failed", failureReason, rawReportPath }` per data-model.md `RouteTarget` (research.md §2, §4)
- [X] T005 In `frontend/scripts/lighthouse-check.mjs`, implement the guest pre-flight function that calls `POST {BASE_URL}/api/proxy/auth/guest`, extracts the `guest_id` claim from the response, and throws a descriptive error when the call fails or the endpoint is unreachable (research.md §3; spec.md edge case "guest access fails")
- [X] T006 In `frontend/scripts/lighthouse-check.mjs`, implement CLI argument parsing for `--url` (default `http://frontend_prod:3000`) and `--routes` (default `/,/articles,/graph,/tags`), per contracts/cli-interface.md

**Checkpoint**: Guest pre-flight, single-route execution, Chrome resolution, and CLI parsing all work in isolation — ready to be wired into the end-to-end flows below.

---

## Phase 3: User Story 1 - 一鍵完成關鍵路徑效能檢查 (Priority: P1) 🎯 MVP

**Goal**: Running one command obtains guest access automatically and audits every configured route, reporting per-route Performance/LCP/TBT/CLS or a clear failure reason — no manual login step.

**Independent Test**: Run `make lighthouse-check` against a running stack (per quickstart.md §1) and confirm a `✅`/`❌` progress line and a raw Lighthouse JSON file appear for every configured route, with zero manual credential entry.

### Implementation for User Story 1

- [X] T007 [US1] In `frontend/scripts/lighthouse-check.mjs`, wire the main run flow: parse args (T006) → run guest pre-flight (T005), aborting the whole process with exit code 1 and no output directory if it fails (spec.md edge case) → for each configured route, call the single-route runner (T004) sequentially → print one `✅ <path>` / `❌ <path> (<reason>)` line per route to stdout as it completes (contracts/cli-interface.md)
- [X] T008 [US1] Add the `lighthouse-check` target to `Makefile`, with `LIGHTHOUSE_URL ?= http://frontend_prod:3000` / `LIGHTHOUSE_ROUTES ?= /,/articles,/graph,/tags` variables and body `docker compose run --rm -v "$(CURDIR)/lighthouse-reports:/app/lighthouse-reports" frontend node scripts/lighthouse-check.mjs --url "$(LIGHTHOUSE_URL)" --routes "$(LIGHTHOUSE_ROUTES)"`, per contracts/cli-interface.md
- [X] T009 [US1] In `frontend/scripts/lighthouse-check.mjs`, ensure a single route's failure (non-zero `lighthouse` exit, timeout, or unparseable JSON output) is caught and recorded as `status: "failed"` with a human-readable `failureReason`, without aborting the remaining routes in the loop (spec.md edge case, FR-010)

### Tests for User Story 1

- [X] T010 [P] [US1] Add unit tests for `extractRouteMetrics` in `frontend/tests/unit/lighthouse-report.test.ts`, using a realistic fixture LHR JSON object and asserting the mapped `performanceScore`/`lcpMs`/`tbtMs`/`cls` values match data-model.md's mapping

**Checkpoint**: User Story 1 is fully functional on its own — a developer can run the check and see per-route pass/fail with raw metrics, even before User Story 2's consolidated report exists.

---

## Phase 4: User Story 2 - 繁體中文彙整報告 (Priority: P2)

**Goal**: All routes from one run are consolidated into a single, Traditional-Chinese Markdown report persisted to disk — no raw JSON reading required to understand results.

**Independent Test**: Run the check (per quickstart.md §3) and open `lighthouse-reports/<runId>/report.md`; confirm a summary table covering every route, Traditional-Chinese headings/labels throughout, and any failed route clearly flagged with a reason rather than omitted.

### Implementation for User Story 2

- [X] T011 [US2] In `frontend/scripts/lib/lighthouse-report.mjs`, implement `renderConsolidatedReport(run, routeTargets)` producing the Markdown shape defined in contracts/report-format.md: header block (timestamp, `BASE_URL`, `guest_id`, success/failure count), a summary table with one row per route (`—` columns + Traditional-Chinese reason for failed routes), and one `###` per-route section with a link to that route's raw JSON
- [X] T012 [US2] In `frontend/scripts/lighthouse-check.mjs`, after the route loop (T007) completes: generate a UTC-timestamp `runId` (`YYYYMMDD-HHMMSS`) so repeated runs never collide (spec.md edge case "run twice in a row"), create `lighthouse-reports/<runId>/`, move each route's raw LHR JSON into it, call `renderConsolidatedReport` (T011) and write `report.md`, then print the final `報告已產出：lighthouse-reports/<runId>/report.md` stdout line (contracts/cli-interface.md)

### Tests for User Story 2

- [X] T013 [P] [US2] Add unit tests for `renderConsolidatedReport` in `frontend/tests/unit/lighthouse-report.test.ts` covering: an all-success run, a mixed success/failure run (failed row renders `—` + a Traditional-Chinese reason per contracts/report-format.md), and an assertion that every heading/table-header string in the output is Traditional Chinese

**Checkpoint**: User Stories 1 and 2 together deliver the complete local workflow from the original request — guest-aware check in, single Traditional-Chinese report out.

---

## Phase 5: User Story 3 - CI 整合 (Priority: P3) ✅ Implemented

**Goal**: The same check runs unattended from GitHub Actions and its report is retrievable by a reviewer without local reproduction.

**Independent Test**: Trigger `lighthouse.yml` via `workflow_dispatch`, or push to a PR and let `ci.yml`'s `lighthouse-check` job run after `deploy-staging-frontend` succeeds; confirm it completes without manual input and that `lighthouse-reports` is downloadable from the run's artifacts.

- [X] T014 [US3] Add `.github/workflows/lighthouse.yml` as a reusable workflow (`workflow_call` + `workflow_dispatch`) and a `lighthouse-check` job in `.github/workflows/ci.yml` (`needs: deploy-staging-frontend`, PR-only) that invokes it against `vars.FRONTEND_URL` — deviates from the original plan of bringing up `postgres`/`redis`/`backend`/`frontend_prod` via `docker compose` inside the runner; hitting the already-deployed staging frontend directly over the public internet is simpler and more representative (see spec.md Assumptions, "CI target environment")
- [X] T015 [US3] In that job, upload `lighthouse-reports/` as a workflow artifact via `actions/upload-artifact@v4` so a reviewer can download the report from the run without repo/local access (spec.md SC-005)
- [X] T016 [P] [US3] CI trigger decided: PR-only (via `ci.yml`'s `lighthouse-check` job, gated on `deploy-staging-frontend`), plus on-demand via `workflow_dispatch` on `lighthouse.yml` directly — not scheduled. Documented in `specs/022-lighthouse-performance-check/quickstart.md` §5.

**Checkpoint**: All three user stories are independently functional. `vars.FRONTEND_URL` must still be configured manually in repo Settings → Secrets and variables → Actions → Variables before `lighthouse-check` can run on a PR; until then it fails fast with a clear error rather than silently skipping.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the feature end-to-end and keep project documentation in sync.

- [X] T017 [P] Run `specs/022-lighthouse-performance-check/quickstart.md` end-to-end (all applicable sections) and confirm every documented outcome actually holds
- [X] T018 [P] Add a `make lighthouse-check` row to the "Backend / Scraper (Python)" or a new small table in `CLAUDE.md`'s Commands section, matching the existing table format
- [X] T019 Confirm `lighthouse`'s own stdout/stderr noise (Chrome/DevTools warnings, progress spinners) doesn't corrupt the `✅`/`❌` progress-line contract from T007 — add `--quiet` or redirect as needed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup (T001's `lighthouse` dependency must exist before T004 can shell out to it) — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion. No dependency on US2/US3.
- **User Story 2 (Phase 4)**: Depends on Foundational completion, and on US1's route loop (T007) existing to consolidate — implemented after US1 but conceptually independent (a US1-only build already works without it).
- **User Story 3 (Phase 5)**: Depends on US1 and US2 both being complete (plan.md Summary: CI integration is deliberately last).
- **Polish (Phase 6)**: Depends on whichever stories are in scope for a given delivery being complete.

### Parallel Opportunities

- T001 and T002 (Setup) can run in parallel.
- T003 (metrics extraction) can be built in parallel with T004–T006 (different concerns within the same foundational phase), though T004–T006 land in the same file (`lighthouse-check.mjs`) so should be done sequentially by one person/agent.
- T010 (US1 tests) and T013 (US2 tests) can run in parallel with each other once their respective implementation tasks land, since they touch the same test file but cover disjoint functions — coordinate to avoid edit conflicts if run concurrently.
- T017–T019 (Polish) can all run in parallel.

---

## Parallel Example: Foundational Phase

```bash
Task: "Implement extractRouteMetrics in frontend/scripts/lib/lighthouse-report.mjs"
Task: "Add lighthouse-reports/ to .gitignore"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (User Story 1).
3. **STOP and VALIDATE**: run `make lighthouse-check` against a local stack per quickstart.md §1–§2 and confirm per-route metrics/failures are visible (raw JSON is enough at this stage — the polished report isn't required yet).

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. User Story 1 → validate independently → this alone already satisfies the "does the check work at all" question.
3. User Story 2 → validate independently (quickstart.md §3) → this is what makes the tool's output actually shareable/useful day-to-day.
4. User Story 3 → deferred; pick up once US1+US2 have been used locally for a while and have proven reliable (plan.md Summary, spec.md Assumptions).

---

## Notes

- [P] tasks touch different files or independent concerns within a shared file — verify no overlapping edits before running them concurrently.
- No TDD ordering is used on this project — implement first, add the corresponding test task from the same phase afterward.
- File paths above are exact; no `[NEEDS CLARIFICATION]` remains in this feature's design docs, so no task here is blocked on an open question except T016 (CI trigger cadence), which is itself the task that resolves it.
