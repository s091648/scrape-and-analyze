---

description: "Task list for Exception Handling Guideline & API Status Code Management"
---

# Tasks: Exception Handling Guideline & API Status Code Management

**Input**: Design documents from `/specs/017-exception-handling-guideline/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/error-response.md, quickstart.md

**Tests**: Every phase below includes dedicated test tasks — mandatory per project constitution §III (Docker-only execution via `make test`/`make test-integration`; not optional even though this feature's spec didn't request TDD explicitly).

**Phase ordering note**: Spec priorities are US1=P1, US2=P2, US3=P2, but US1's own acceptance scenarios (spec.md) require the central exception→status mapping described by US3 to already exist — there is no way to deliver "consistent API error responses" before the mechanism that produces them exists. Phases below are therefore ordered by dependency, not raw priority: **Phase 3 = US3 (the mechanism)**, **Phase 4 = US1 (applying it to routers/guards — the P1 outcome)**, **Phase 5 = US2 (the guideline document, independent of the other two and safe to do in parallel)**. This is called out again in the Dependencies section.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup

**Purpose**: Confirm nothing new needs installing; no project scaffolding required — this feature extends existing `src/` and `backend/` trees only.

- [x] T001 Confirm `sentry-sdk` (in the `observability` dependency group, not `backend`) is importable in the resolved environment — verify with `docker compose run --rm backend uv run python -c "import sentry_sdk"` (the `backend` service's `uv sync` installs into a uv-managed environment only reachable via `uv run`, not the container's plain `python`; confirmed present, `backend/Dockerfile.dev`'s own `CMD` already invokes `uv run uvicorn ...`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared exception taxonomy every subsequent phase raises/catches. Nothing else in this feature compiles or has anything meaningful to test without this.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 Add 6 shared exception categories (`ValidationError`, `NotFoundError`, `ConflictError`, `UnauthorizedError`, `ForbiddenError`, `ExternalDependencyError`), each subclassing `DomainError`, in `src/shared/domain/exceptions.py` (data-model.md §1)
- [x] T003 [P] Retrofit existing `src/modules/collection/domain/exceptions.py` leaf classes (`InvalidUrlHashError`, `InvalidScraperKeywordTypeError`, `UnsupportedSourceTypeError`, `InvalidScraperIntervalError`) to additionally inherit the new shared `ValidationError` (multiple inheritance alongside existing `CollectionDomainError`)
- [x] T004 [P] Retrofit existing `src/modules/intelligence/domain/exceptions.py` leaf classes (`InvalidSuggestionStatusError`, `InvalidSimilarityScoreError`, `InvalidWeeklyReportStatusError`) to additionally inherit the new shared `ValidationError` (multiple inheritance alongside existing `IntelligenceDomainError`)
- [x] T005 [P] Unit tests for the new shared exception hierarchy in `src/tests/unit/shared/domain/test_exceptions.py`: each new category subclasses `DomainError`; each retrofitted leaf class (T003, T004) is `isinstance` of both its bounded-context root AND `ValidationError`
- [x] T006 Add `SENTRY_DSN` read (mirroring the pattern already used for other env vars) to `backend/config.py`; it already exists in `.env.example` but `backend/` currently never reads it (research.md §4)

**Checkpoint**: Foundation ready — the exception vocabulary exists and is tested; US3 (mechanism) can now be built on top of it.

---

## Phase 3: User Story 3 - A maintained mapping from domain errors to HTTP status codes (Priority: P2, built first — see phase-ordering note above)

**Goal**: A single, centrally-registered mapping so any `DomainError` raised anywhere produces the correct HTTP status and response body, with zero per-router status-code logic.

**Independent Test**: Unit-test the exception handler function directly against each shared category (no router/HTTP call needed) — confirms the mapping is correct and complete before any router is touched.

### Tests for User Story 3

- [x] T007 [P] [US3] Unit test in `backend/tests/test_exception_handlers.py`: each shared category (`NotFoundError`→404, `ConflictError`→409, `UnauthorizedError`→401, `ForbiddenError`→403, `ValidationError`→400, `ExternalDependencyError`→502) maps to its documented status code, and an unmapped/plain `DomainError` falls back to 500 (FR-007)
- [x] T008 [P] [US3] Unit test in `backend/tests/test_exception_handlers.py`: response body for every mapped status matches the `ErrorResponse` contract shape `{"error": {"code", "message", "request_id"}}` (contracts/error-response.md), `error.code` is the fixed per-category `SCREAMING_SNAKE_CASE` string, and `error.request_id` equals the request's `X-Request-ID` value
- [x] T009 [P] [US3] Unit test in `backend/tests/test_exception_handlers.py`: for a 500/502 response, `error.message` is a fixed generic string (never `str(exception)`, a stack trace, a file path, or raw SQL text) — FR-009 / SC-003
- [x] T010 [US3] Unit test in `backend/tests/test_exception_handlers.py`: a non-`DomainError` exception (e.g. a raw `sqlalchemy.exc.IntegrityError` reaching the boundary untranslated) is still caught by the safety-net handler and returns 500 with the same sanitized shape (Edge Case in spec.md)
- [x] T011 [US3] Unit test in `backend/tests/test_exception_handlers.py`: `sentry_sdk.capture_exception` is called for every 500/502-mapped exception (mock `sentry_sdk`), and is NOT called for 400/401/403/404/409 (expected/recoverable errors are not error-tracked as bugs)

### Implementation for User Story 3

- [x] T012 [P] [US3] Create `backend/schemas/error.py` with the `ErrorResponse` Pydantic schema (`error.code: str`, `error.message: str`, `error.request_id: str`) per data-model.md §3
- [x] T013 [US3] Create `backend/exceptions/handlers.py` (new module) implementing: (a) the ordered category→status dict from data-model.md §2, (b) an `isinstance`-based most-specific-first lookup function, (c) an `@app.exception_handler(DomainError)` that builds the `ErrorResponse` body (reading `request_id` from the current `structlog` contextvars set by `RequestLoggingMiddleware`, per research.md §3), calls `sentry_sdk.capture_exception` for any category mapped to 500/502, and never includes `str(exception)` in the body for those categories, (d) an `@app.exception_handler(Exception)` safety net for non-`DomainError` exceptions, same sanitized 500 response + Sentry capture (depends on T002, T012)
- [x] T014 [US3] Register both handlers via `app.add_exception_handler(...)` in `backend/main.py`, and add `sentry_sdk.init(dsn=SENTRY_DSN)` at module top level, gated on `SENTRY_DSN` being non-empty (no-op fallback per Constitution's graceful-degradation rule) — depends on T006, T013

**Checkpoint**: Any code that raises a `DomainError` subclass now produces the correct, sanitized, traceable HTTP response — verifiable in isolation without any router changes yet.

---

## Phase 4: User Story 1 - Consistent error responses from the API (Priority: P1) 🎯 MVP outcome

**Goal**: Every endpoint in `backend/routers/` — including auth guards — actually uses the mechanism from Phase 3, so a real API consumer sees consistent, correct status codes instead of the current per-endpoint ad hoc behavior.

**Independent Test**: Call each audited endpoint with not-found / invalid-input / conflicting / unauthorized inputs and confirm the status code and body match the documented mapping (spec.md Acceptance Scenarios 1–5).

### Tests for User Story 1

- [x] T015 [P] [US1] Test in `backend/tests/test_guards_optional_user.py` (extend existing file): `require_admin`/`require_user`/token-decode failures now raise `UnauthorizedError`/`ForbiddenError` and produce 401/403 via the central handler, not a direct `HTTPException`
- [x] T016 [P] [US1] Test in `backend/tests/test_articles.py` (extend existing file): requesting a nonexistent article ID returns 404 via `NotFoundError` + the `ErrorResponse` shape (spec.md Acceptance Scenario 1)
- [x] T017 [P] [US1] Test in `backend/tests/test_auth.py` (extend existing file): registering a duplicate email/username, or linking an already-linked Google account, returns 409 via `ConflictError` — replacing the current `"duplicate" in str(e).lower()` string-matching (research.md §7)
- [x] T018 [US1] Full-audit regression test in `backend/tests/test_error_response_audit.py` (new): parameterized across every route enumerated in the FR-010 audit (T019), asserting each returns a status from the documented mapping (not a hardcoded ad hoc value) for a representative failure input — SC-001

### Implementation for User Story 1

- [x] T019 [US1] Produce the FR-010 router audit as `specs/017-exception-handling-guideline/router-audit.md`: one row per existing `HTTPException`/`status_code=` occurrence across the 12 routers (101 occurrences confirmed via `grep` in `backend/routers/`) recording current vs. required behavior (data-model.md §4) — do this before the remaining tasks in this phase so T020–T025 have a concrete checklist to work from
- [x] T020 [US1] Migrate `backend/auth/guards.py`: replace the 7 direct `raise HTTPException(401/403, ...)` call sites with `raise UnauthorizedError(...)` / `raise ForbiddenError(...)` (research.md §6) — depends on T002, T014
- [x] T021 [US1] Migrate `backend/routers/auth.py`: replace inline `HTTPException(404/409, ...)` calls and the `"duplicate"/"unique" in str(e).lower()` string-matching with `NotFoundError`/`ConflictError` raises (new leaf classes added to `src/modules/collection/domain/exceptions.py` or an appropriate module as identified in T019) — depends on T002, T014, T019
- [x] T022 [P] [US1] Migrate `backend/routers/articles.py`, `backend/routers/topics.py`, `backend/routers/scraper_keywords.py`, `backend/routers/tags.py` to raise the appropriate shared-category exception instead of inline `HTTPException`, per T019's audit — depends on T002, T014, T019
- [x] T023 [P] [US1] Migrate `backend/routers/llm_providers.py`, `backend/routers/scraper_settings.py`, `backend/routers/metric_definitions.py`, `backend/routers/weekly_reports.py`, `backend/routers/user.py` to raise the appropriate shared-category exception instead of inline `HTTPException`, per T019's audit — depends on T002, T014, T019
- [x] T024 [US1] In `backend/routers/chat.py`: translate a `None` result from `ChatCompletionService`/`ResilientLLMService` (all providers exhausted) into `ExternalDependencyError` at the point it's treated as an unrecoverable failure — for the pre-stream-start path, let it flow through the central handler (502); for the SSE in-stream path (`generate()`'s existing `except Exception` block), keep emitting an in-band `{"error": ...}` event using the same `error.code`/`error.message` vocabulary as the contract, since the HTTP status is already committed (contracts/error-response.md "Streaming exception" clause) — depends on T002, T014
- [x] T025 [US1] ~~In the weekly-report image pipeline call site that consumes a resilient provider's `None` result...~~ **Resolved as N/A, documented in router-audit.md**: the multimodal image provider (`src/bootstrap.py`) is a single directly-injected provider, not a `Resilient*Service` chain with a `None`-on-exhaustion contract like `ResilientLLMService`/`ResilientMetricsService`; `generate_weekly_report.py` already catches image-generation failures as a non-fatal warning (report is published without a cover image) — a deliberate degrade-gracefully design, not an unrecoverable failure needing `ExternalDependencyError`. It also runs in the CLI/background `weekly-report` job with no HTTP response to map a status code onto. No code change made.
- [x] T026 [US1] Update `backend/routers/*.py` OpenAPI response documentation (`responses={...}` on route decorators) to reference `ErrorResponse` (T012) for the status codes each endpoint can now produce, so Swagger UI reflects the real behavior (the original motivation named in GitHub issue #41) — depends on T012, T020–T025. **Done** via a new `error_responses(*status_codes)` helper in `backend/schemas/error.py`, applied to every migrated endpoint in `articles.py`, `auth.py`, `tags.py`, `llm_providers.py`, `metric_definitions.py`, `scraper_keywords.py`, `scraper_settings.py`, `topics.py` (business-error codes per router-audit.md, plus 401/403 for `Depends(require_admin)` and 401 for `Depends(require_user)`); see router-audit.md's "T026 follow-up" note.

**Checkpoint**: User Stories 3 AND 1 together deliver the spec's P1 outcome — Swagger/API consumers now see accurate, consistent status codes. This is the MVP.

---

## Phase 5: User Story 2 - A written guideline developers can follow when writing new code (Priority: P2)

**Goal**: A durable, discoverable document a contributor can consult instead of guessing or waiting for review feedback.

**Independent Test**: Hand the document to someone implementing a new use case/endpoint; confirm they can answer "raise or not / which exception / how does it propagate" without asking a maintainer (spec.md Independent Test).

### Tests for User Story 2

- [x] T027 [P] [US2] Add a VitePress build-compatibility check: run the site's production build command against `site/guide/architecture/exception-handling.md` (T028) and confirm no bare `<...>` outside fenced code blocks breaks the build (Constitution Principle VII) — document the command used in `quickstart.md` if not already present

### Implementation for User Story 2

- [x] T028 [US2] Write `site/guide/architecture/exception-handling.md` covering: (a) when to raise vs. return a non-exception failure signal (FR-001), (b) which exception types are permitted at each layer (FR-002), (c) propagation rules across domain → application → infrastructure → API boundaries, including the infra→domain translation rule (FR-003), (d) the shared category taxonomy and how to add a new leaf class (FR-004, FR-004a), (e) the 400-vs-422 rule (FR-012, research.md §5), (f) the "expected/recoverable vs. programmer-error" distinction (FR-011) — can be drafted in parallel with Phase 3/4 but MUST be updated to match whatever T013/T019 actually implement before this task is considered done
- [x] T029 [US2] Add a one-line cross-reference to `site/guide/architecture/exception-handling.md` under CLAUDE.md's "Key Conventions" section — depends on T028

**Checkpoint**: All three user stories delivered — mechanism (US3), applied consistently (US1), documented (US2).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verification sweep once all stories are integrated.

- [x] T030 Run `make uml-backend` to confirm the new `backend/exceptions/handlers.py` module doesn't break the auto-generated architecture diagram's layer classification (Constitution Principle VIII)
- [x] T031 [P] Run `make test` and `make test-integration` (Docker-only, Constitution §III) and confirm all new and existing tests pass, including the T018 full-audit regression test. **Confirmed**: `make test-backend` (389 passed), `make test-src` (746 passed), `make test-backend-integration` (224 passed, against local postgres). `src/` integration tests not run (require live LLM provider API keys per CLAUDE.md, unrelated to this feature's changes).
- [x] T032 Manually run the `curl` verification steps in `quickstart.md` against a locally running `docker compose up` stack. **Confirmed** against `docker compose up -d backend postgres`: 404 (`GET /articles/{uuid}`), 401 (invalid bearer on `/scraper-settings`), 409 (duplicate `/auth/register`) all returned the documented `{"error": {"code", "message", "request_id"}}` shape. Fixed `quickstart.md`'s stale example (`GET /topics/{id}` doesn't exist — no such route) to use working examples and note the one known gap: a request with *no* `Authorization` header at all is rejected by FastAPI's `HTTPBearer` before reaching our guard code, so it 401s with FastAPI's own `{"detail": "Not authenticated"}` shape rather than the `ErrorResponse` contract (status code is still correct).
- [x] T033 [P] Update the 2 frontend call sites reading `data?.detail` in `frontend/app/settings/settings-page-content.tsx:158,178` to read `data?.error?.message` instead (research.md §8) — non-blocking optional follow-up; explicitly confirmed safe to defer, include here only if time allows within this feature's delivery

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS everything else (the exception classes T002–T004 are imported by every later phase)
- **US3 (Phase 3)**: Depends on Foundational. Independently testable/deliverable on its own (T007–T011 need no router changes).
- **US1 (Phase 4)**: Depends on Foundational AND on US3 (Phase 3) being complete — US1's routers raise exceptions that only produce correct responses once the Phase 3 handler is registered. This is the one deliberate cross-story dependency in this feature (documented in the phase-ordering note above); it exists because US1 is the *outcome* of the mechanism US3 *is*.
- **US2 (Phase 5)**: Depends only on Foundational for the exception vocabulary to document accurately; the writing task (T028) can start in parallel with Phase 3/4 but must be reconciled with what was actually built (T013, T019) before it's considered complete. Does not block or get blocked by US1.
- **Polish (Phase 6)**: Depends on Phases 3, 4, and 5 all being complete.

### Parallel Opportunities

- T003 and T004 (retrofitting the two existing bounded-context exception files) are independent files — parallel.
- T007, T008, T009 (three distinct test assertions in the same new test file but independent test functions) — parallel authoring, sequential file writes; treat as parallel-safe since they're additive to the same file.
- T012 (schema) can start alongside T007–T011 (tests) since both only depend on T002.
- T022 and T023 (disjoint sets of router files) — parallel.
- T028 (guideline draft) can run in parallel with all of Phase 3/4, since a first draft only needs the Phase 2 vocabulary — just requires a final reconciliation pass (captured as part of T028's own definition-of-done) once Phase 3/4 land.

---

## Parallel Example: Phase 3 (US3)

```bash
# Launch all three independent test-assertion tasks together:
Task: "Unit test: category → status mapping in backend/tests/test_exception_handlers.py"
Task: "Unit test: ErrorResponse shape + request_id correlation in backend/tests/test_exception_handlers.py"
Task: "Unit test: 500/502 message sanitization in backend/tests/test_exception_handlers.py"

# In parallel with the tests, start the schema:
Task: "Create ErrorResponse Pydantic schema in backend/schemas/error.py"
```

---

## Implementation Strategy

### MVP Scope

The MVP for this feature is **Phase 2 + Phase 3 + Phase 4 together** (not Phase 3 alone) — the spec's P1 outcome (US1, "consistent error responses") is only observable once the mechanism (US3) is both built AND applied to real routers/guards. Phase 5 (US2, the guideline document) delivers independent value and can ship before, during, or after the MVP without blocking it.

### Incremental Delivery

1. Setup + Foundational (Phase 1–2) → exception vocabulary exists and is tested
2. US3 (Phase 3) → mechanism exists and is independently verified correct — no visible API change yet
3. US1 (Phase 4) → mechanism applied to guards + all 12 routers → **MVP**: Swagger/API consumers see accurate status codes (the outcome named in GitHub issue #41)
4. US2 (Phase 5) → guideline published, safe to land any time after Phase 2
5. Polish (Phase 6) → verification sweep, optional frontend follow-up
