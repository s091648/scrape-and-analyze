# Tasks: API Rate Limiting & Generated Frontend Types

**Input**: Design documents from `/specs/026-rate-limit-codegen/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Mandatory per constitution §III — every user story below has a dedicated test sub-phase, written first. Backend tests are pytest unit tests with a mocked Redis client (`unittest.mock.AsyncMock`), mirroring the existing pattern in `backend/tests/test_chat_router.py::make_mock_redis`/`patch("backend.routers.chat._make_redis", ...)` — no real Redis or DB required. Frontend already has one `*-api.test.ts` file per `frontend/lib/api/*.ts` file (e.g. `topics-api.test.ts`); those existing suites are the regression safety net for the US4 migration tasks and are not being rewritten, just kept green.

**Organization**: Tasks are grouped by user story (from spec.md, in priority order) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps to spec.md's User Story 1–5

## Path Conventions

Web application layout per plan.md: `backend/` (FastAPI), `frontend/` (Next.js), `shared/` (cross-service domain code), `scripts/` (repo-root tooling). All paths below are exact, per plan.md's Project Structure section.

---

## Phase 1: Setup

**Purpose**: Scaffolding needed before any foundational or story work

- [X] T001 Create `backend/rate_limit/` package (`backend/rate_limit/__init__.py`), mirroring the shape of the existing `backend/auth/` package
- [X] T002 [P] Add a types-only OpenAPI→TypeScript generator as a `frontend/package.json` devDependency (run `npm install` inside the frontend Docker container per project convention, not on host)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure that MUST be complete before any user story can be implemented. Split into two independent tracks (rate-limiting infra blocks US1–US3; codegen infra blocks US4–US5) — both tracks can proceed in parallel with each other, but each story still waits on its own track.

**⚠️ CRITICAL**: No user story work can begin until its track's tasks below are complete

### Rate-limiting infra (blocks US1, US2, US3)

- [X] T003 [P] Add `RateLimitExceededError(DomainError)` to `shared/domain/exceptions.py`
- [X] T004 [P] Add `retry_after_seconds: Optional[int] = None` field to `ErrorBody` in `backend/schemas/error.py`
- [X] T005 Register `(RateLimitExceededError, 429, "RATE_LIMIT_EXCEEDED")` in `_CATEGORY_MAPPING` in `backend/exceptions/handlers.py` (depends on T003)
- [X] T006 [P] Unit test: a raised `RateLimitExceededError` produces a `429` response with `code == "RATE_LIMIT_EXCEEDED"`, is logged at `warning`, and is NOT sent to Sentry (matching the existing 4xx `DomainError` treatment) — extend `backend/tests/test_exception_handlers.py` (depends on T005)
- [X] T007 [P] Add `RATE_LIMIT_GUEST_TOKEN_MAX`/`_WINDOW_SECONDS`, `RATE_LIMIT_AUTH_ATTEMPT_MAX`/`_WINDOW_SECONDS`, `RATE_LIMIT_CHAT_BURST_MAX`/`_WINDOW_SECONDS`, `RATE_LIMIT_SEARCH_MAX`/`_WINDOW_SECONDS` env vars (each with a sane default) to `backend/config.py`
- [X] T008 [P] Implement the shared client-origin extraction helper (`X-Forwarded-For` first hop, falling back to `request.client.host`) in `backend/rate_limit/client_origin.py` (depends on T001)
- [X] T009 Implement the Rate Limit Policy registry (`guest_token`, `auth_attempt`, `chat_burst`, `search` — each with `key_dimension`, `max_requests`, `window_seconds`) in `backend/rate_limit/policies.py` (depends on T007, T001)
- [X] T010 Implement the Redis fixed-window limiter core (`INCR`/`EXPIRE` against `REDIS_URL`, mirroring `chat_service.py::RateLimitService`) plus per-policy `Depends()` factories, with fail-open + warning log on Redis error, in `backend/rate_limit/limiter.py` (depends on T003, T008, T009)
- [X] T011 [P] Refactor `backend/routers/languages.py`, `backend/routers/bootstrap.py`, and `backend/services/auth_service.py::compute_guest_id` to call the new `client_origin` helper instead of their own duplicated `X-Forwarded-For`/`request.client.host` logic (depends on T008)

### Codegen infra (blocks US4, US5)

- [X] T012 [P] Implement `scripts/export_openapi_schema.py` — imports the FastAPI `app` object, writes `app.openapi()` to `backend/openapi.json`, and writes a coverage-gap report listing endpoints without a full request/response Pydantic schema
- [X] T013 [P] Configure the OpenAPI→TS generator (config/npm script) to read `backend/openapi.json` and emit `frontend/lib/api/generated-types.ts` (depends on T002)
- [X] T014 Add a `generate-api-types` Makefile target that runs the export (T012) then the generation (T013) in sequence (depends on T012, T013)

**Checkpoint**: Foundation ready — US1, US2, US3 can start once the rate-limiting track is done; US4, US5 can start once the codegen track is done. The two tracks don't block each other.

---

## Phase 3: User Story 1 - Anonymous credential issuance is throttled (Priority: P1) 🎯 MVP

**Goal**: `POST /auth/guest` refuses excess guest-credential requests from the same origin within a rolling window, without affecting other origins.

**Independent Test**: Issue repeated `POST /auth/guest` requests from a single origin in a short window; requests beyond `RATE_LIMIT_GUEST_TOKEN_MAX` come back `429`/`RATE_LIMIT_EXCEEDED` while a request from a different `X-Forwarded-For` origin still succeeds.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T015 [P] [US1] Unit test: the `guest_token` policy allows requests within its limit, refuses excess requests from the same origin key, and leaves a different origin key unaffected — `backend/tests/test_rate_limit.py`
- [X] T016 [P] [US1] Unit test: `POST /auth/guest` returns `429` with `error.code == "RATE_LIMIT_EXCEEDED"` and a `retry_after_seconds` once the policy is exceeded — `backend/tests/test_auth.py`

### Implementation for User Story 1

- [X] T017 [US1] Wire `Depends(guest_token_limit)` onto `POST /auth/guest` in `backend/routers/auth.py` (depends on T010; makes T015/T016 pass)

**Checkpoint**: User Story 1 is fully functional and independently testable/deployable (SC-001).

---

## Phase 4: User Story 2 - Login, registration, and token-refresh attempts are throttled (Priority: P1)

**Goal**: `POST /auth/verify`, `/auth/register`, `/auth/google/authorize`, `/auth/refresh`, `/auth/guest/refresh` all refuse excess attempts from the same origin, evaluated before the submitted credentials are checked.

**Independent Test**: Repeatedly submit requests to any of the five endpoints from one origin; requests beyond `RATE_LIMIT_AUTH_ATTEMPT_MAX` come back `429`/`RATE_LIMIT_EXCEEDED` regardless of whether the submitted credentials would otherwise have been valid.

### Tests for User Story 2

- [X] T018 [P] [US2] Unit test: the `auth_attempt` policy refuses excess attempts from the same origin key regardless of payload validity — `backend/tests/test_rate_limit.py`
- [X] T019 [P] [US2] Unit test: each of `POST /auth/verify`, `/auth/register`, `/auth/google/authorize`, `/auth/refresh`, `/auth/guest/refresh` returns `429`/`RATE_LIMIT_EXCEEDED` once that shared per-origin limit is exceeded, and the refusal happens before the request body is validated against domain rules — `backend/tests/test_auth.py`

### Implementation for User Story 2

- [X] T020 [US2] Wire `Depends(auth_attempt_limit)` onto `POST /auth/verify`, `POST /auth/register`, `POST /auth/google/authorize`, `POST /auth/refresh`, `POST /auth/guest/refresh` in `backend/routers/auth.py` (depends on T010; same file as T017, run after it; makes T018/T019 pass)

**Checkpoint**: User Stories 1 AND 2 both work independently (SC-002).

---

## Phase 5: User Story 3 - Bursts on costly authenticated features are smoothed out (Priority: P2)

**Goal**: `POST /chat/completions`, `GET /search`, `GET /search/autocomplete` each refuse a short-window burst from one identity, independent of chat's existing daily quota.

**Independent Test**: From one authenticated/guest identity, send a rapid burst to `/chat/completions` (or `/search`) faster than the short-window limit; excess requests come back `429`/`RATE_LIMIT_EXCEEDED` while `GET /chat/quota`'s daily allowance is left untouched.

### Tests for User Story 3

- [X] T021 [P] [US3] Unit test: the `chat_burst` policy allows requests within its limit and refuses short-window excess for one identity, independent of the existing daily-quota counter key — `backend/tests/test_rate_limit.py`
- [X] T022 [P] [US3] Unit test: `POST /chat/completions` returns `429`/`RATE_LIMIT_EXCEEDED` on a burst while `GET /chat/quota`'s reported daily remaining/limit is unaffected — `backend/tests/test_chat_router.py`
- [X] T023 [P] [US3] Unit test: `GET /search` and `GET /search/autocomplete` refuse excess requests per identity within the window, and a compliant pace is never refused — `backend/tests/test_search_router.py`

### Implementation for User Story 3

- [X] T024 [US3] Wire `Depends(chat_burst_limit)` onto `POST /chat/completions` in `backend/routers/chat.py`, and refactor its existing hand-rolled `HTTPException(429, ...)` daily-quota branch to raise `RateLimitExceededError` instead (research.md Decision 3) (depends on T010, T005; makes T021/T022 pass)
- [X] T025 [P] [US3] Wire `Depends(search_limit)` onto `GET /search` and `GET /search/autocomplete` in `backend/routers/search.py` (depends on T010; makes T023 pass)

**Checkpoint**: All rate-limiting stories (US1–US3) independently functional — SC-001, SC-002, SC-003 verifiable end-to-end.

---

## Phase 6: User Story 4 - Frontend API types are generated from the backend contract (Priority: P1)

**Goal**: `frontend/lib/api/generated-types.ts` is produced from `backend/openapi.json`, and every existing hand-written interface in `frontend/lib/api/*.ts` is replaced with an import from it.

**Independent Test**: Change a backend `response_model` field, run `make generate-api-types`, confirm the change appears in `generated-types.ts` with no hand edit, and confirm `frontend/lib/api/*.ts` call sites still compile.

### Tests for User Story 4

- [X] T026 [P] [US4] Add a smoke test asserting `frontend/lib/api/generated-types.ts` exists and exports the expected top-level shape (e.g. a `Topic`-equivalent schema entry with its known fields) — `frontend/tests/unit/generated-types.test.ts` (fails until T027 runs generation)

### Implementation for User Story 4

- [X] T027 [US4] Run `make generate-api-types` to produce `backend/openapi.json` and `frontend/lib/api/generated-types.ts` (depends on T014; makes T026 pass)
- [X] T028 [P] [US4] Migrate `frontend/lib/api/topics.ts`: replace the hand-written `Topic` interface with an import from `generated-types.ts`; `frontend/tests/unit/topics-api.test.ts` must still pass unmodified (depends on T027)
- [X] T029 [P] [US4] Migrate `frontend/lib/api/articles.ts` the same way; `frontend/tests/unit/articles-api.test.ts` must still pass (depends on T027)
- [X] T030 [P] [US4] Migrate `frontend/lib/api/tags.ts` the same way; `frontend/tests/unit/tags-api.test.ts` must still pass (depends on T027)
- [X] T031 [P] [US4] Migrate `frontend/lib/api/auth.ts` the same way; `frontend/tests/unit/auth-api.test.ts` must still pass (depends on T027)
- [X] T032 [P] [US4] Migrate `frontend/lib/api/user.ts` the same way; `frontend/tests/unit/user-api.test.ts` must still pass (depends on T027)
- [X] T033 [P] [US4] ~~Migrate~~ `frontend/lib/api/graph.ts` — SKIPPED: `backend/openapi-coverage-gap.md` confirms none of `/graph`, `/analyses/graph`, `/analyses/graph/group/{name}` have a defined response schema (no `response_model` in `backend/routers/graph.py`); left hand-written per FR-013/spec.md's Assumptions (depends on T027)
- [X] T034 [P] [US4] Migrate `frontend/lib/api/search.ts` the same way; `frontend/tests/unit/search-api.test.ts` must still pass (depends on T027)
- [X] T035 [P] [US4] Migrate `frontend/lib/api/weekly-reports.ts` the same way; `frontend/tests/unit/weekly-reports-api.test.ts` must still pass (depends on T027)
- [X] T036 [P] [US4] Migrate `frontend/lib/api/scraper-settings.ts` the same way; `frontend/tests/unit/scraper-settings-api.test.ts` must still pass (depends on T027)
- [X] T037 [P] [US4] Migrate `frontend/lib/api/scraper-keywords.ts` the same way; `frontend/tests/unit/scraper-keywords-api.test.ts` must still pass (depends on T027)
- [X] T038 [P] [US4] Migrate `frontend/lib/api/llm-providers.ts` the same way; `frontend/tests/unit/llm-providers-api.test.ts` must still pass (depends on T027)
- [X] T039 [P] [US4] Migrate `frontend/lib/api/metric-definitions.ts` the same way; `frontend/tests/unit/metric-definitions-api.test.ts` must still pass (depends on T027)
- [X] T040 [P] [US4] Migrate `frontend/lib/api/analytics.ts` the same way; `frontend/tests/unit/analytics-api.test.ts` must still pass (depends on T027)
- [X] T041 [P] [US4] ~~Migrate~~ `frontend/lib/api/source-categories.ts` — SKIPPED: `GET /source-categories` has no defined response schema (coverage-gap report); left hand-written (depends on T027)
- [X] T042 [P] [US4] ~~Migrate~~ `frontend/lib/api/grafana.ts` — SKIPPED: all 8 `/grafana/*` endpoints have no defined response schema (coverage-gap report); left hand-written (depends on T027)
- [X] T043 [US4] Run `cd frontend && npm run build` to confirm every migrated call site typechecks against the generated types (depends on T028–T042)

**Checkpoint**: User Stories 1–4 all independently functional — the core drift-elimination value is delivered (SC-004, SC-005).

---

## Phase 7: User Story 5 - Drift between backend contract and frontend types is caught automatically (Priority: P2)

**Goal**: A backend contract change submitted without regenerating `frontend/lib/api/generated-types.ts` is automatically flagged before merge.

**Independent Test**: Change a backend `response_model`, deliberately skip regeneration, and confirm the same check CI runs (re-run `make generate-api-types` + `git diff --exit-code`) fails locally.

### Tests for User Story 5

- [X] T044 [P] [US5] Test: two consecutive runs of `scripts/export_openapi_schema.py` against an unchanged `app` produce byte-identical output (regeneration is idempotent, FR-010) — `backend/tests/test_export_openapi_schema.py`
- [X] T045 [US5] Test: the coverage-gap report from `scripts/export_openapi_schema.py` lists `/auth/register` (raw `dict` body, no Pydantic request schema) as not covered by generation — `backend/tests/test_export_openapi_schema.py` (depends on T012, T044 — same file as T044, run after it)

### Implementation for User Story 5

- [X] T046 [US5] Add steps to the `frontend-unit` stage of `.github/workflows/ci.yml` that re-run `make generate-api-types`'s two commands, then on a same-repo PR auto-commit+push any diff back onto the PR branch (`[skip ci]`) instead of failing; fork PRs / direct pushes to `master` still fail with a message pointing at `make generate-api-types` (depends on T014, T027, T044) — see research.md Decision 8's "Correction" for why this ended up auto-fixing rather than just failing

**Checkpoint**: All 5 user stories independently functional and mutually compatible — SC-006 verifiable (a stale-regeneration PR is caught by CI).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Behavior that spans every rate-limit policy, not any single story

- [X] T047 [P] Unit test: when the Redis client raises a connection error during a policy check, the request is allowed through (fail open) and the failure is logged at `warning` — `backend/tests/test_rate_limit.py` (depends on T010)
- [X] T048 [P] Register `specs/026-rate-limit-codegen`'s pages (Spec, Plan, Data Model, Tasks, Research, Quick Start, Requirements, and both contracts) in `site/.vitepress/config.js`'s sidebar, mirroring the existing `025-iac-provisioning` entry's shape
- [ ] T049 Execute `quickstart.md`'s rate-limiting and generated-types validation steps end-to-end against a running `docker compose up` stack and confirm every step's expected outcome — **NOT DONE**: Docker Desktop wasn't running in this session (see completion report). Equivalent coverage obtained instead via direct `uv run pytest`/`vitest`/`tsc` runs on host (630/632 backend unit tests, 163 frontend unit tests, full typecheck diff all clean) — still recommend running this for real once Docker is available, since it's the only check that exercises the actual `docker compose` service wiring (REDIS_URL host resolution, the `job_service`/`frontend` container mounts the Makefile target relies on, etc.)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup; its two tracks (rate-limiting T003–T011, codegen T012–T014) can run in parallel with each other but each blocks its own stories
- **User Stories 1–3 (Phases 3–5)**: Depend on the rate-limiting Foundational track (T003–T011)
- **User Stories 4–5 (Phases 6–7)**: Depend on the codegen Foundational track (T012–T014); US5 additionally depends on US4's T027 (generation must have run once before drift can be checked)
- **Polish (Phase 8)**: Depends on the rate-limiting stories (T010) being in place

### User Story Dependencies

- **US1 (P1)**: No dependency on other stories
- **US2 (P1)**: No dependency on US1, but shares `backend/routers/auth.py` — T020 runs after T017 to avoid a merge conflict in the same file, not because it's logically blocked
- **US3 (P2)**: No dependency on US1/US2
- **US4 (P1)**: No dependency on US1/US2/US3
- **US5 (P2)**: Depends on US4 (needs at least one successful generation, T027, before "detect drift" is meaningful)

### Parallel Opportunities

- T003–T011 (rate-limiting Foundational) and T012–T014 (codegen Foundational) are two independent tracks — a second contributor can start the codegen track while the first works the rate-limiting track
- Within Foundational, every task marked [P] can run in parallel with the other [P] tasks in the same track
- Once its Foundational track is done: US1, US2, US3's *implementation* tasks (T017, T020, T024, T025) can be staffed in parallel by different contributors (US2's just needs to land after US1's in `auth.py`). Their *test* tasks (T015, T018, T021) all write to the same new `backend/tests/test_rate_limit.py`, though, along with Polish's T047 — treat that file the same way as `auth.py`: whoever adds to it next does so on top of the others' additions rather than in a simultaneous, independent edit
- T028–T042 (the 15 per-file frontend migrations) are all `[P]` — fully parallelizable, one contributor/agent per file

---

## Parallel Example: User Story 4

```bash
# After T027 (generation has run), launch all per-file migrations together:
Task: "Migrate frontend/lib/api/topics.ts to import from generated-types.ts"
Task: "Migrate frontend/lib/api/articles.ts to import from generated-types.ts"
Task: "Migrate frontend/lib/api/tags.ts to import from generated-types.ts"
# ...and the remaining 12 files (T031–T042), all independent of each other
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2's rate-limiting track (T003–T011)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: confirm guest-token issuance is throttled per `quickstart.md` step 1–3
5. Deploy/demo if ready — this alone closes the single highest-leverage gap identified in the originating discussion

### Incremental Delivery

1. Setup + rate-limiting Foundational → US1 → validate → deploy (MVP)
2. + US2 → validate → deploy (auth brute-force protection complete)
3. + US3 → validate → deploy (chat/search burst protection complete — all rate limiting done)
4. Setup + codegen Foundational → US4 → validate → deploy (type drift eliminated for covered endpoints)
5. + US5 → validate → deploy (drift now caught automatically in CI — feature complete)

### Parallel Team Strategy

With two contributors: one takes the rate-limiting track (Foundational → US1 → US2 → US3), the other takes the codegen track (Foundational → US4 → US5) — the two tracks touch entirely disjoint files (`backend/rate_limit/`, `backend/routers/{auth,chat,search}.py` vs. `scripts/export_openapi_schema.py`, `frontend/lib/api/*`) until Phase 8's `quickstart.md` validation, which needs both done.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Verify each story's tests fail before implementing that story
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently
- Same-file touch points across otherwise-parallel tasks: T017/T020 (`backend/routers/auth.py`), T024/T025's shared dependency on `backend/rate_limit/limiter.py`, T015/T018/T021/T047 (`backend/tests/test_rate_limit.py`), and T044/T045 (`backend/tests/test_export_openapi_schema.py`) — sequence those as noted above; everything else in a track is safe to parallelize
