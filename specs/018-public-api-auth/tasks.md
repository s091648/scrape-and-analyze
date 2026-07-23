---

description: "Task list for Public API Endpoint Authentication"
---

# Tasks: Public API Endpoint Authentication

**Input**: Design documents from `/specs/018-public-api-auth/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/guest-token.md, quickstart.md

**Tests**: Every phase below includes dedicated test tasks — mandatory per project constitution §III (Docker-only execution via `make test-backend`/`make test-frontend`; not optional even though not explicitly requested in the spec).

**Phase ordering note**: Spec priorities are US1=P1, US2=P1, US3=P2, but they cannot ship independently of each other the way a normal priority order implies. Attaching the new guard to any router simultaneously (a) rejects tokenless requests (US1) and (b) is the only way to prove a guest token actually grants access (US2's Independent Test) — the two are one mechanism, not two. Per research.md §9, gating a router without the guest-token mechanism already existing would 401 the current production frontend for every anonymous visitor. Phases below are therefore ordered by dependency, mirroring the same pattern `017-exception-handling-guideline` used for its own forced-together stories: **Phase 3 = US2 (the mechanism — issuance/refresh endpoints + the guard function, proven in isolation)**, **Phase 4 = US1 (the mechanism applied to every in-scope router + frontend wiring — the outcome, deployed atomically with Phase 3)**, **Phase 5 = US3 (regression verification that existing logged-in flows are untouched)**. This is called out again in the Dependencies section.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup

**Purpose**: Confirm the one new technical capability this feature needs (backend-side JWT signing) actually works in this environment before building on it.

- [x] T001 Confirm `python-jose`'s `jwt.encode` works in the `backend` service's resolved environment — verify with `docker compose run --rm backend uv run python -c "from jose import jwt; print(jwt.encode({'a': 1}, 'x', algorithm='HS256'))"` (per Constitution: Docker-only execution; note `uv run` is required — plain `python` inside this container does not see the `uv`-managed environment)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared guest-claim vocabulary and verification logic every subsequent phase builds on. Nothing else in this feature has anything meaningful to test without this.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 Add guest-claim helpers to `backend/services/auth_service.py`: `compute_guest_id(request: Request) -> str` (extract/adapt the existing `sha256(ip + user_agent)[:16]` logic currently inline in `backend/routers/chat.py::_guest_identity`, per research.md §3), `create_guest_access_token(guest_id: str) -> str` (`{"tier": "guest", "guest_id", "token_use": "access", "exp": now+1h}`, signed with `NEXTAUTH_SECRET`/HS256 via `jose.jwt.encode`), `create_guest_refresh_token(guest_id: str) -> str` (same shape, `"token_use": "refresh"`, `exp`=now+30d) — per data-model.md §1–2
- [x] T003 [P] Add `backend/schemas/guest.py` with `GuestTokenPairOut` (`access_token: str`, `refresh_token: str`, `expires_in: int`), `GuestAccessTokenOut` (`access_token: str`, `expires_in: int`), and `GuestRefreshRequest` (`refresh_token: str`) Pydantic models — per contracts/guest-token.md
- [x] T004 Add `require_any_token` to `backend/auth/guards.py`, following the existing `_require_admin_impl`/`require_admin` two-part pattern: decode the bearer token with `NEXTAUTH_SECRET`; accept if the payload has a `role` claim (existing real user/admin token, exactly what `_require_user_impl` already accepts) OR has `"tier": "guest"` and `token_use` is absent or `"access"`; otherwise `raise UnauthorizedError(...)` — including when `token_use == "refresh"` (research.md §2) — depends on T002
- [x] T005 [P] Unit tests for T002's claim helpers in `backend/tests/test_auth_service.py` (new or extend if it exists): `create_guest_access_token`/`create_guest_refresh_token` produce the documented claim shapes and expiry deltas (1h / 30d); `compute_guest_id` is deterministic for the same ip+user-agent and differs for a different ip or user-agent
- [x] T006 [P] Unit tests for `require_any_token` in `backend/tests/test_guards.py` (extend existing file): accepts a real user token, accepts a real admin token, accepts a guest access token, rejects a guest refresh token (`token_use == "refresh"`), rejects a garbage/malformed token, rejects a missing token, rejects an expired guest access token — depends on T004

**Checkpoint**: Foundation ready — guest-claim vocabulary and the accept/reject decision exist and are tested in isolation; no router is wired to any of this yet, so there is no production behavior change so far.

---

## Phase 3: User Story 2 - Anonymous site visitors keep browsing without registering (Priority: P1, built first — see phase-ordering note above)

**Goal**: A caller with no account can obtain a valid guest token pair with zero credentials, and that token is proven to grant access — the mechanism spec.md US1's gate depends on existing first.

**Independent Test**: Request a guest token pair from the backend with no prior login, then present the access token to a `require_any_token`-gated route and confirm it succeeds — verifiable without any production router having been migrated yet (T009 mounts a throwaway test route, mirroring the pattern `017-exception-handling-guideline`'s `test_exception_handlers.py` already uses for isolated handler testing).

### Tests for User Story 2

- [x] T007 [P] [US2] Test `POST /auth/guest` in `backend/tests/test_auth.py` (extend existing file): returns `200` with `access_token`/`refresh_token`/`expires_in`; decoding both tokens shows the same `guest_id` claim; requires no `Authorization` header
- [x] T008 [P] [US2] Test `POST /auth/guest/refresh` in `backend/tests/test_auth.py`: a valid, non-expired refresh token → `200` with a new access token carrying the same `guest_id`; an expired refresh token, a malformed token, and an access token presented where a refresh token is expected all → `401` via the standard `ErrorResponse` shape (contracts/guest-token.md)
- [x] T009 [US2] Independent-test-style integration test (new `backend/tests/test_guest_token_flow.py`): mount a throwaway `@app.get("/__test/guest-gated")` route behind `Depends(require_any_token)` (same pattern as `test_exception_handlers.py`'s `/__test/raise/{category}`); full round trip — call `POST /auth/guest`, use the returned access token against the throwaway route → `200`; call it with no token → `401`; call it with the *refresh* token → `401` — depends on T004, T010, T011

### Implementation for User Story 2

- [x] T010 [US2] Implement `POST /auth/guest` in `backend/routers/auth.py`: no request body, calls `compute_guest_id(request)` + T002's token helpers, returns `GuestTokenPairOut` — depends on T002, T003
- [x] T011 [US2] Implement `POST /auth/guest/refresh` in `backend/routers/auth.py`: takes `GuestRefreshRequest`, decodes the refresh token (reject via `UnauthorizedError` if malformed/expired/wrong `token_use`, reusing `require_any_token`'s style of check rather than duplicating it — factor the shared decode step if natural), mints a new access token with the same `guest_id`, returns `GuestAccessTokenOut` — depends on T002, T003
- [x] T012 [P] [US2] Frontend: extend `frontend/lib/providers/guest-mode-provider.tsx` (or add a sibling provider colocated with it) to acquire a guest token pair via `POST /auth/guest` (through `apiFetch`) whenever `useSession()` resolves to no authenticated user and no cached pair exists; store the pair in `sessionStorage` (consistent with this provider's existing storage choice); expose the current guest access token through context — depends on T010
- [x] T013 [US2] Frontend: silent refresh in the same provider — on the guest access token nearing/reaching its 1h expiry (or on a `401` from a call made with it), call `POST /auth/guest/refresh`; if that also fails (expired refresh token), fall back to T012's full re-issuance — all transparent to the visitor (spec.md User Story 2, Scenarios 3–4) — depends on T012
- [x] T014 [P] [US2] Frontend unit tests (Vitest) for the provider in `frontend/tests/unit/`: acquires a token when unauthenticated, reuses the cached token within its lifetime, does not acquire one when a real session exists, refreshes on expiry, falls back to full re-issuance when refresh also fails

**Checkpoint**: A caller with no account can obtain and use a working guest token; the frontend can acquire/refresh one transparently. No production router is gated yet — still zero behavior change for real traffic.

---

## Phase 4: User Story 1 - External API consumer without a token can no longer read data (Priority: P1) 🎯 MVP outcome

**Goal**: Every endpoint enumerated in spec.md FR-001 actually rejects a request with no valid token, and the existing frontend keeps working for every anonymous/guest/logged-in flow because it now attaches the token from Phase 3.

**Independent Test**: Call each in-scope endpoint with no `Authorization` header and confirm `401`; call it again with a guest token and confirm it still succeeds (spec.md Acceptance Scenarios 1–3).

### Tests for User Story 1

- [x] T015 [US1] Full-audit regression test in `backend/tests/test_error_response_audit.py` (extend, mirroring `017-exception-handling-guideline`'s equivalent audit task): parameterized across every route identified in T017's audit, asserting `401` with no token and success with a guest token
- [x] T016 [P] [US1] Test in `backend/tests/test_chat_router.py` (extend): `/chat/completions` and `/chat/quota` now `401` with no token; with a guest token, the guest tier's rate-limit key comes from the token's `guest_id` claim (not the retired `__rag_gid` cookie/ip-hash); existing per-tier limits (`DAILY_LIMIT_GUEST`/`DAILY_LIMIT_USER`) are unchanged

### Implementation for User Story 1

- [x] T017 [US1] Produce a short audit as `specs/018-public-api-auth/router-audit.md`: one row per endpoint in the routers named in spec.md FR-001 (`articles.py`, `graph.py`, `tags.py`'s read-only endpoints, `topics.py`'s `GET /topics`, `weekly_reports.py`, `languages.py`, `chat.py`), confirming it currently has no auth dependency and recording that `require_any_token` will be added — do this before T018–T023 so they have a concrete checklist (mirrors `017-exception-handling-guideline`'s `router-audit.md` precedent)
- [x] T018 [US1] Apply `require_any_token` to `backend/routers/articles.py`'s public endpoints per T017's audit (`GET /articles`, `GET /source-categories`, the 3 `filters/*` endpoints, `GET /articles/{article_id}`, `POST /articles/{article_id}/view`) — `POST /admin/articles/flush-view-counts` already requires `require_admin` and is out of scope — depends on T004, T017
- [x] T019 [P] [US1] Apply `require_any_token` to both endpoints in `backend/routers/graph.py` — depends on T004, T017
- [x] T020 [P] [US1] Apply `require_any_token` to `backend/routers/tags.py`'s read-only endpoints (`GET /tag-groups`, `GET /tag-groups/{group_id}`) — every other endpoint in this router already requires `require_admin`/`require_user` and is untouched — depends on T004, T017
- [x] T021 [P] [US1] Apply `require_any_token` to `GET /topics` in `backend/routers/topics.py` — write endpoints already require `require_admin` and are untouched — depends on T004, T017
- [x] T022 [P] [US1] Apply `require_any_token` to all four endpoints in `backend/routers/weekly_reports.py` — depends on T004, T017
- [x] T023 [P] [US1] Apply `require_any_token` to `GET /languages` in `backend/routers/languages.py` — depends on T004, T017
- [x] T024 [US1] Migrate `backend/routers/chat.py`: add `require_any_token` to `/chat/completions` and `/chat/quota`; extend `_parse_identity` (or the identity-resolution path) to also recognize `"tier": "guest"` tokens and read `guest_id` directly from the decoded claim; delete `_guest_identity()` and all `__rag_gid` cookie get/set code (research.md §7, spec.md FR-007) — depends on T004, T002
- [x] T025 [US1] Frontend: add `token?: string` + the existing `authHeader(token)`/`authHeaders(token)` pattern (already used by `lib/api/scraper-settings.ts`, `lib/api/auth.ts`) to every currently-tokenless call site for an in-scope endpoint (`lib/api/articles.ts`, the graph call site, `lib/api/tags.ts`'s read functions, `lib/api/topics.ts`'s list function, the weekly-reports call site, the languages call site, the chat call sites), sourcing the token from T012's provider (the real NextAuth session token when logged in, otherwise the guest access token) — depends on T012
- [x] T026 [US1] Update the OpenAPI `responses=` documentation on every endpoint touched by T018–T024 to include `401` via `error_responses()` (from `017-exception-handling-guideline`'s `backend/schemas/error.py`), consistent with that feature's own OpenAPI-documentation task — depends on T018–T024

**Checkpoint**: Every endpoint in FR-001's scope now rejects tokenless requests, and the frontend transparently keeps every existing anonymous/guest/logged-in flow working. This phase MUST deploy together with Phase 3 (research.md §9) — this is the MVP.

---

## Phase 5: User Story 3 - Existing logged-in users and admins are unaffected (Priority: P2)

**Goal**: Prove the blanket "require a token" change added nothing on top of the existing `require_admin`/`require_user` checks — no re-authentication, no new prompt, no role-logic change.

**Independent Test**: Call an in-scope endpoint and an already-`require_admin`-gated endpoint with an existing real user/admin token and confirm both succeed exactly as before this feature (spec.md Acceptance Scenarios).

### Tests for User Story 3

- [x] T027 [P] [US3] Regression sweep in `backend/tests/test_error_response_audit.py` (extend further, or a new `backend/tests/test_guest_auth_regression.py`): an existing real user JWT and an existing real admin JWT succeed unchanged on (a) every endpoint newly gated in Phase 4 and (b) every endpoint that already required `require_admin`/`require_user` before this feature — confirming `role` is still read only from `models.auth.User.role` via the unchanged decode path, with no new check introduced
- [x] T028 [P] [US3] Frontend test (Vitest, extend T014's suite): the provider from T012 never attempts guest-token acquisition when `useSession()` reports an authenticated user — no extra network call, no visible change for logged-in sessions

**Checkpoint**: All three user stories delivered — mechanism (US2), applied consistently (US1), verified not to regress existing sessions (US3).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verification sweep once all stories are integrated.

- [x] T029 Run `make test-backend` and `make test-frontend` (Docker-only, Constitution §III) and confirm all new and existing tests pass, including the T015 full-audit regression test
- [x] T030 [P] Manually run the `curl` verification steps in `quickstart.md` against a locally running `docker compose up` stack
- [x] T031 Update `CLAUDE.md`'s "Backend Routers" table: change the auth column for `articles.py`, `graph.py`, `languages.py`, `weekly_reports.py`, and the read-only rows of `tags.py`/`topics.py` from "Public" to reflect the new `require_any_token` requirement (guest or logged-in) — keeps the doc accurate per this repo's established convention of documenting real router behavior
- [x] T032 [P] Run `make uml-backend` to confirm the new guard/service functions don't break the auto-generated architecture diagram's layer classification (Constitution Principle VIII)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS everything else (T002's claim helpers and T004's guard are imported by every later phase)
- **US2 (Phase 3)**: Depends on Foundational. Independently testable/deliverable on its own via a throwaway test route (T009) — no production router changes yet.
- **US1 (Phase 4)**: Depends on Foundational AND on US2 (Phase 3) being complete — US1's routers rely on guest tokens already being obtainable, or the current production frontend's anonymous visitors would be locked out the moment a router is gated. This is the one deliberate cross-story dependency in this feature (documented in the phase-ordering note above), mirroring `017-exception-handling-guideline`'s US3→US1 precedent.
- **US3 (Phase 5)**: Depends on US1 (Phase 4) — there is nothing to regression-test against until the newly-gated endpoints exist. Verification-only; introduces no new production code.
- **Polish (Phase 6)**: Depends on Phases 3, 4, and 5 all being complete.

### Parallel Opportunities

- T005 and T006 (independent test files, both depend only on T002/T004) — parallel.
- T007 and T008 (independent test functions in the same file but additive) — parallel-safe.
- T019–T023 (disjoint router files, each only depends on T004 + T017's audit) — parallel.
- T014 (frontend provider tests) can start once T012/T013 land, independent of backend Phase 4 progress.
- T027 and T028 (backend regression sweep vs. frontend regression test, disjoint files) — parallel.

---

## Parallel Example: Phase 4 (US1)

```bash
# After T017's audit and T004 (guard) are done, gate the disjoint routers together:
Task: "Apply require_any_token to backend/routers/graph.py"
Task: "Apply require_any_token to backend/routers/tags.py's read-only endpoints"
Task: "Apply require_any_token to GET /topics in backend/routers/topics.py"
Task: "Apply require_any_token to backend/routers/weekly_reports.py"
Task: "Apply require_any_token to GET /languages in backend/routers/languages.py"
```

---

## Implementation Strategy

### MVP Scope

The MVP for this feature is **Phase 2 + Phase 3 + Phase 4 together** (not Phase 3 alone) — the spec's P1 outcome (US1, "external consumer can no longer read data for free") is only safe to ship once the mechanism (US2) that keeps legitimate anonymous/guest traffic working already exists. Phase 5 (US3, regression verification) is required before calling the MVP done, but adds no new production behavior.

### Incremental Delivery

1. Setup + Foundational (Phase 1–2) → guest-claim vocabulary and guard exist and are unit-tested — no visible change yet
2. US2 (Phase 3) → guest-token mechanism exists and is independently verified correct (via a throwaway test route) — still no production router gated
3. US1 (Phase 4) → mechanism applied to every in-scope router + frontend wiring → **MVP**: external consumers without a token are refused; existing anonymous/guest/logged-in flows keep working — Phase 3 and Phase 4 deploy together, not as separate releases
4. US3 (Phase 5) → regression verification, safe to land immediately after Phase 4
5. Polish (Phase 6) → verification sweep, doc accuracy, UML regeneration

---

## Implementation Notes (discovered during T001–T032)

Three real, pre-existing or newly-introduced bugs were found and fixed along the way — none were separately-numbered tasks, but all were necessary for the feature to actually satisfy its own FRs:

- **`POST /admin/articles/flush-view-counts` was never actually admin-gated.** `backend/routers/articles.py` imported `require_admin` inside the function body but never wired it as a `Depends(...)` — a pre-existing dead-import bug, unrelated to this feature but discovered while auditing `articles.py` for T017/T018. Fixed by wiring the already-imported dependency; `backend/tests/integration/test_article_view_counts.py`'s flush tests updated to pass an admin token accordingly.
- **Missing-`Authorization`-header requests bypassed the `ErrorResponse` contract.** `backend/auth/guards.py`'s `bearer = HTTPBearer()` (default `auto_error=True`) rejected a totally-missing header itself, before any guard function ran, producing FastAPI's own `{"detail": "Not authenticated"}` shape instead of the `{"error": {...}}` contract spec.md FR-008 requires. Fixed by switching to `HTTPBearer(auto_error=False)` and having `require_admin`/`require_user`/`require_any_token` raise `UnauthorizedError` themselves on a `None` token.
- **`require_user` would have silently accepted a guest token.** `_require_user_impl` only checked `exp`, never that the token actually represented a real user — a guest token (no `sub` claim) would pass it and then crash downstream (e.g. `backend/routers/user.py`'s `_get_user_id` doing `UUID(user["sub"])`) with a raw `KeyError` instead of a clean 401. Fixed by rejecting `payload.get("tier") == "guest"` in `_require_user_impl`, per FR-003's "must continue to be refused" requirement.

Frontend implementation centralizes token attachment in `apiFetch` (`frontend/lib/api/client.ts`) via a small module-level store (`frontend/lib/auth-token-store.ts`) that `AuthTokenProvider` keeps in sync, rather than threading a `token` param through every `lib/api/*.ts` call site individually — every existing call site that doesn't already set its own `Authorization` header benefits automatically. This is a deliberate refinement over research.md §8's original "extend the per-call-site pattern" framing, chosen because nearly every endpoint now needs a token (unlike when only a few admin endpoints did).
