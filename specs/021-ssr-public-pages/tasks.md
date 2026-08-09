# Tasks: SSR Conversion for Public Pages (LCP Fix)

**Input**: Design documents from `/specs/021-ssr-public-pages/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Included per project constitution §III (mandatory test phase). Frontend unit → `frontend/tests/unit/` (Vitest); Frontend E2E → `frontend/tests/integration/` (Playwright).

**Organization**: Tasks are grouped by user story (spec.md priorities: US1/US3 = P1, US2 = P2, US4 = P3) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffolding shared by every later phase — no story-specific logic yet.

- [X] T001 [P] Create `frontend/lib/cookies/constants.ts` exporting `TOPIC_COOKIE_NAME = 'selectedTopicId'`, `LOCALE_COOKIE_NAME = 'locale'`, and `PREFERENCE_COOKIE_MAX_AGE_SECONDS = 31536000` (isomorphic — no `'use client'`/`'use server'` directive, safe to import from both client and server code), per `contracts/ssr-preference-cookies.md`
- [X] T002 [P] Create `frontend/lib/cookies/set-preference-cookie.ts` with a client-only `setPreferenceCookie(name: string, value: string)` helper that writes `document.cookie` with `Path=/; Max-Age=<PREFERENCE_COOKIE_MAX_AGE_SECONDS>; SameSite=Lax` (and `Secure` when `location.protocol === 'https:'`), importing the constants from T001
- [X] T003 [P] Create `frontend/lib/server/ssr-fetch.ts` skeleton (implemented directly, in full, rather than stubbed — see T004-T007): server-only module (top-of-file comment noting it must never be imported from a `'use client'` file), with TypeScript types `SsrContext { credential: string | null; topicId: string | null; locale: string }` and exported function signatures (bodies `throw new Error('not implemented')` for now) for `resolveSsrContext()`, `fetchArticlesListSSR`, `fetchGraphSSR`, `fetchTagGroupsSSR`, `fetchWeeklyReportSSR`, matching `contracts/ssr-data-fetch.md`

**Checkpoint**: Shared types/constants exist; no runtime behavior yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The credential/topic/language resolution every one of the 4 routes needs identically (research.md decisions 1–2, data-model.md). **No user story's SSR fetch can produce real content until this phase is complete.**

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Implement the credential-resolution half of `resolveSsrContext()` in `frontend/lib/server/ssr-fetch.ts`: call `getServerSession(authConfig)` (import from `frontend/lib/auth.ts`, same call `frontend/app/admin/monitoring/page.tsx` already makes); if a session exists, use `session.accessToken` as the credential; otherwise `null` — **does not** call `POST /auth/guest` (research.md "Server-side credential resolution reuses session tokens only" — calling it would bypass the existing anonymous-visitor paywall gate, discovered and corrected during Phase 3/4 implementation)
- [X] T005 Implement the topic-resolution half of `resolveSsrContext()` in `frontend/lib/server/ssr-fetch.ts`: read the `selectedTopicId` cookie via `cookies()` from `next/headers` (name from T001's constants), call `GET /topics` with the resolved credential to validate it's a real, active topic id; fall back to `null` (no-filter/first-active, matching `topic-provider.tsx`'s existing default logic) when the cookie is absent, malformed, or not found in the topic list (depends on T004)
- [X] T006 Implement the language-resolution half of `resolveSsrContext()` in `frontend/lib/server/ssr-fetch.ts`: read the `locale` cookie via `cookies()`; if present and one of `SUPPORTED_LANGUAGES` (mirror the list from `backend/services/language_service.py`), use it; otherwise call `GET ${BACKEND_URL}/languages` with the resolved credential, forwarding the real client IP via `X-Forwarded-For` (read from `headers()` in `next/headers`) (research.md "Server-side language resolution reuses `GET /languages`") (depends on T004)
- [X] T007 Wrap `resolveSsrContext()` and all four `fetchXSSR` stubs in `frontend/lib/server/ssr-fetch.ts` with try/catch that returns `null` on any error (network failure, non-2xx, credential-issuance failure) instead of throwing — FR-007, research.md "SSR fetch failure fallback" (depends on T004, T005, T006)
- [X] T008 [P] Unit tests for `resolveSsrContext()` in `frontend/tests/unit/ssr-fetch.test.ts`: session-token reuse, null credential (and zero backend calls) when there is no session, topic cookie valid/missing/pointing-at-deleted-topic, locale cookie valid/missing/unsupported (triggers `GET /languages` call), all with mocked `fetch`/`cookies()`/`headers()`/`getServerSession` (depends on T004, T005, T006, T007)

**Checkpoint**: `resolveSsrContext()` fully working and tested — every user story below can now build its route-specific fetch on top of it.

---

## Phase 3: User Story 1 - First-time visitor sees articles immediately (Priority: P1) 🎯 MVP

**Goal**: `/` and `/articles` render their primary content in the initial server-rendered HTML for **authenticated** visitors (per spec.md's User Story 3 revision, anonymous visitors deliberately do not get server-fetched real content — see Phase 4).

**Independent Test**: With an authenticated session cookie set, load `/articles` (and `/`) with JavaScript disabled/blocked and confirm real content (article cards / weekly report) is present in the raw HTML response — see `quickstart.md` step 2.

### Tests for User Story 1

- [X] T015 [P] [US1] *(scope adjusted during implementation — see `ssr-first-paint.spec.ts`'s header comment)* `page.route()` cannot intercept the Next.js server's own outgoing fetch to `BACKEND_URL` (only browser-originated requests), and whether an authenticated session's SSR fetch actually reaches real backend data further depends on this run's session JWT matching whatever `NEXTAUTH_SECRET` the real backend container was started with — neither is under this suite's control. Covered instead: `frontend/tests/integration/ssr-first-paint.spec.ts`'s "renders without a server error" cases (FR-007 structural check, all 4 routes, authenticated) + `quickstart.md` step 2 (manual curl-based verification with real seed data, as originally documented there)
- [X] T016 [P] [US1] *(scope adjusted — see above)* Covered instead at the component level, fully deterministic and independent of any real backend: `frontend/tests/unit/articles-page-content-ssr-seed.test.tsx` — asserts `fetchArticles` (the client-side call) is never invoked on mount when seeded with `initialArticles`, is invoked normally when not seeded, and resumes firing once a real dependency (topic) changes after a seeded mount

### Implementation for User Story 1

- [X] T009 [P] [US1] Implement `fetchArticlesListSSR(params)` in `frontend/lib/server/ssr-fetch.ts`: calls `GET ${BACKEND_URL}/articles` with the query built from `params` and the resolved credential/locale from `resolveSsrContext()`, wrapped per T007's failure handling
- [X] T010 [P] [US1] Implement `fetchWeeklyReportSSR(topicId)` in `frontend/lib/server/ssr-fetch.ts`: calls `GET ${BACKEND_URL}/weekly-reports/latest` with the resolved credential/locale, wrapped per T007
- [X] T011 [US1] Convert `frontend/app/articles/page.tsx` into an `async function ArticlesPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> })` Server Component: resolve `searchParams`, build the same query `usePagination()`/`fetchSearchParamsString` build today, call `fetchArticlesListSSR`, and render `<ArticlesPageContent initialArticles={...} initialTotal={...} />` (depends on T009)
- [X] T012 [US1] Modify `frontend/app/articles/articles-page-content.tsx`: accept `initialArticles`/`initialTotal` props, seed `useState` from them instead of `[]`/`0`, and guard the existing fetch `useEffect` (lines ~80-105) so it does not re-fire on mount when the current params already match what was server-seeded — it should still fire normally when the user changes a filter/page/sort afterward (depends on T011)
- [X] T013 [US1] Convert `frontend/app/page.tsx` into an async Server Component: call `fetchWeeklyReportSSR` (topic resolved via `resolveSsrContext()`), render `<HomePageContent initialReport={...} />` (depends on T010)
- [X] T014 [US1] Modify `frontend/components/features/weekly-report/weekly-report-widget.tsx` (rendered from `frontend/app/home-page-content.tsx`) to accept an optional initial-report prop and seed its internal state from it instead of always starting from its existing fetch-on-mount effects (`weekly-report-widget.tsx:110-192`); pass it through from `home-page-content.tsx` (depends on T013)

**Checkpoint**: `/` and `/articles` fully server-render default-state content, with no duplicate client fetch, for authenticated visitors.

---

## Phase 4: User Story 3 - Anonymous visitor sees the same paywalled placeholder instantly, with no content leak (Priority: P1)

**Goal** *(revised — see spec.md User Story 3 and research.md)*: Prove that an anonymous visitor (no session, regardless of `sessionStorage` guest-mode opt-in, which the server cannot see) never receives server-fetched real content, and that post-hydration client behavior — including the existing guest-mode fetch-on-opt-in and the `sessionStorage` guest-token flow — is completely unaffected by SSR.

**Independent Test**: A browser with no prior cookies/localStorage/sessionStorage (or any combination without a real session) loads `/articles`; the response HTML contains the existing placeholder/paywall content, not real articles. After hydration, interacting with the page (including clicking "Continue as Guest") behaves exactly as it does today.

### Tests for User Story 3

- [X] T017 [P] [US3] *(reframed — see spec.md's User Story 3 revision: pre-hydration state is a loading skeleton, not placeholder text, since the paywall/placeholder decision is itself computed client-side from `useSession()`)* `frontend/tests/integration/ssr-first-paint.spec.ts`'s "never embeds real content pre-hydration" cases: fresh, fully anonymous context (no cookies/storage), JS disabled, all 4 routes — asserts the raw HTML contains no real-content markers, fully deterministic (no session ⇒ `resolveSsrContext()` makes zero backend calls, per T019's unit test)
- [X] T018 [P] [US3] Post-hydration "Continue as Guest still works" is already covered end-to-end by the pre-existing `frontend/tests/integration/guest-mode.spec.ts` (confirmed still passing after this feature's changes — see implementation notes); this feature adds no new client-side guest-token code path for that test to exercise differently, so no new duplicate test was added
- [X] T019 [US3] Add a case to `frontend/tests/unit/ssr-fetch.test.ts` (extends T008): confirm `resolveSsrContext()` makes **no** backend call at all (not even an attempt) when there is no session, and that every `fetchXSSR` helper consuming a null-credential context returns `null` immediately per T007 (spec FR-002)

**Checkpoint**: US1 + US3 both independently verified — SSR works for authenticated visitors, and the anonymous-visitor paywall gate is provably unaffected.

---

## Phase 5: User Story 2 - Returning visitor sees their own topic and language on first paint (Priority: P2)

**Goal**: A visitor's previously chosen topic/language is written to the new cookies and honored by the server on the very first rendered frame of their next visit — no hydration-time correction (FR-005/FR-006/FR-008 cookie half).

**Independent Test**: Set the `selectedTopicId` (or `locale`) cookie to a non-default value, request `/articles` fresh (no JS run yet), and confirm the server-rendered HTML reflects that value.

### Tests for User Story 2

- [X] T023 [P] [US2] *(scope adjusted — same real-backend-data/secret-alignment constraint as T015; see `ssr-first-paint.spec.ts` header)* The cookie→topic resolution logic itself (reading the cookie, validating against a live topic list, falling back when stale/missing) is fully covered — deterministically, with mocked `fetch`/`cookies()` — in `frontend/tests/unit/ssr-fetch.test.ts`'s "resolveSsrContext — topic resolution" suite. End-to-end confirmation with real multi-topic data remains a manual `quickstart.md` step 4 exercise
- [X] T024 [P] [US2] *(scope adjusted, same reason)* Covered deterministically in `frontend/tests/unit/ssr-fetch.test.ts`'s "resolveSsrContext — locale resolution" suite (cookie honored, geo-IP fallback, unsupported-cookie fallback). End-to-end confirmation remains a manual `quickstart.md` step 4 exercise
- [X] T025 [P] [US2] Covered by construction rather than a dedicated test: `resolveTopicId`/`resolveLocale` (`ssr-fetch.ts`) fall back to the same no-filter/first-active default and `'en'` a first-ever visitor's client-side code already used pre-cookie — the "no visible swap" property follows directly from both sides sharing that one default, verified via T005/T006's unit tests plus the existing client-side default-selection tests in `frontend/tests/unit/topic-provider.test.tsx`

### Implementation for User Story 2

- [X] T020 [P] [US2] In `frontend/lib/providers/topic-provider.tsx`'s `setSelectedTopicId`, call `setPreferenceCookie(TOPIC_COOKIE_NAME, id)` (from T001/T002) in addition to the existing `localStorage.setItem` call (also backfilled in `loadTopics()`'s initial resolution, so pre-existing localStorage-only visitors pick up the cookie on their very next visit, not just their next explicit topic change)
- [X] T021 [P] [US2] In `frontend/lib/providers/i18n-provider.tsx`, call `setPreferenceCookie(LOCALE_COOKIE_NAME, ...)` from both `setLocale` and the first-ever geo-IP-resolution effect (`i18n-provider.tsx:46-62`, when `resolvedLanguage` is first determined and no `localStorage` value existed yet) so a first-time visitor's client-resolved language is cookie-persisted for their *next* visit
- [X] T022 [US2] Extend T005's topic-cookie resolution in `frontend/lib/server/ssr-fetch.ts` to explicitly cover the "cookie references a deleted/deactivated topic" edge case: confirm `GET /topics`'s response is checked for an exact id match (inactive/deleted topics won't appear) and that the fallback path is identical to a missing cookie (spec Edge Cases) (depends on T005)

**Checkpoint**: US1 + US2 + US3 all independently functional; returning visitors see correct topic/language on first paint.

---

## Phase 6: User Story 4 - Graph and tags views also render server-side (Priority: P3)

**Goal**: `/graph` and `/tags` get the same server-rendered first paint as `/` and `/articles`, via the same shared `resolveSsrContext()` mechanism, without changing either page's existing interactive logic.

**Independent Test**: Load `/graph` and `/tags` with JavaScript disabled and confirm each renders real content (graph data / tag groups) in the raw HTML response.

### Tests for User Story 4

- [X] T032 [P] [US4] *(scope adjusted — same constraint as T015/T023/T024)* Covered by `ssr-first-paint.spec.ts`'s parametrized "never embeds real content pre-hydration" (anonymous) and "renders without a server error" (authenticated) cases, which already loop over all 4 routes including `/graph` and `/tags`

### Implementation for User Story 4

- [X] T026 [P] [US4] Implement `fetchGraphSSR(topicId)` in `frontend/lib/server/ssr-fetch.ts`: calls `GET ${BACKEND_URL}/analyses/graph` with the resolved credential, wrapped per T007
- [X] T027 [P] [US4] Implement `fetchTagGroupsSSR(topicId)` in `frontend/lib/server/ssr-fetch.ts`: calls `GET ${BACKEND_URL}/tag-groups` with the resolved credential, wrapped per T007
- [X] T028 [US4] Create `frontend/app/graph/graph-page-content.tsx`: move the current `frontend/app/graph/page.tsx` body here unchanged (keep `'use client'`), except accept an `initialData` prop and seed the guest-mode `firstPageArticleIds` state from it instead of the current unconditional `fetchArticles` effect (`page.tsx:19-30`) when initial data is present
- [X] T029 [US4] Convert `frontend/app/graph/page.tsx` into an async Server Component that calls `fetchGraphSSR`/`resolveSsrContext()` and renders `<GraphPageContent initialData={...} />` (depends on T026, T028)
- [X] T030 [US4] Create `frontend/app/tags/tags-page-content.tsx`: move the current `frontend/app/tags/page.tsx` body here unchanged (keep `'use client'`), except accept an `initialGroups` prop and seed the `groups` state (`page.tsx:416`) from it instead of `[]`, guarding the existing fetch `useEffect` (`page.tsx:742-754`) the same way T012 guards `articles-page-content.tsx`
- [X] T031 [US4] Convert `frontend/app/tags/page.tsx` into an async Server Component that calls `fetchTagGroupsSSR`/`resolveSsrContext()` and renders `<TagsPageContent initialGroups={...} />` (depends on T027, T030)

**Checkpoint**: All 4 user stories independently functional — full feature scope complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verification and cleanup spanning all stories.

- [X] T033 [P] Effectively confirmed during implementation: an `npx playwright test ssr-first-paint.spec.ts` run happened to execute with `BACKEND_URL` unset (pointing at an unreachable `127.0.0.1:8000` from inside the container — logged `ECONNREFUSED` on every SSR fetch attempt for all 4 routes), and all 8 tests still passed — no crash, no 5xx, graceful degradation held under total backend unavailability (stronger evidence than the originally-planned single manual `/articles` reload). Recommend still running the literal `quickstart.md` step 5 once against `frontend_prod` before merging, since this was incidental rather than a dedicated `frontend_prod` run.
- [ ] T034 [P] **Not run** — requires Lighthouse/Chrome DevTools, a `frontend_prod` build, and a pre-SSR baseline comparison; needs to be done manually by the user per `quickstart.md` step 6.
- [X] T035 [P] Reviewed during implementation — no redundant loading-state flags found. Each seeded component's `isLoading`/`loading`/`graphLoading` state was written to initialize from the presence of seeded data from the start (not added as dead code afterward), so there was nothing left over to clean up.
- [X] T036 **Deliberate, accepted gap — documented, not built. Confirmed load-bearing after a same-day revert attempt.** Test-coverage audit (2026-08-09) confirmed no automated test exercises SSR against a *real running backend*: `ssr-first-paint.spec.ts`'s authenticated-path cases only assert "no 5xx / no error overlay" (Playwright can't intercept the server's own outgoing fetch — see that file's header), and CI's `frontend-e2e` job never starts `postgres`/`backend` at all (confirmed via `.github/workflows/ci.yml`). Tried wiring `playwright.config.ts`'s `webServer.env.BACKEND_URL` to `process.env.BACKEND_URL` (was hardcoded to `http://localhost:8000`) the same day, specifically so `docker compose run --rm frontend npm run test:e2e` could reach the real, already-running `backend` container locally — this broke ~10 pre-existing tests in `articles.spec.ts`/`tags.spec.ts`/`error-handling.spec.ts`, because those tests' `page.route()`-based mocks (browser-side only) get bypassed once SSR can seed real DB content server-side (the 021 seed-guard in `articles-page-content.tsx`/`tags-page-content.tsx` then skips the client-side fetch those tests rely on `page.route()` intercepting). **Reverted the same day** — the hardcoded `localhost:8000` is load-bearing, not an incidental bug: it keeps this Playwright webServer's SSR path deliberately unreachable in every environment (CI and local docker alike), which is what keeps the existing mocked suite deterministic. Building real coverage would require adding `postgres`/`redis`/`backend` services + migrations + seed data to `frontend-e2e`, aligning `NEXTAUTH_SECRET`, *and* reworking the existing mocked suite to tolerate/override SSR-seeded content — evaluated and declined as disproportionate for this feature (user decision, 2026-08-09). Genuine end-to-end verification of real SSR content remains 100% manual, via `quickstart.md` steps 2 and 4 — see that document's "Known limitation" section for the full rationale.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup (T001–T003) — BLOCKS all user stories.
- **User Stories (Phase 3–6)**: All depend on Foundational (Phase 2) completion.
  - US1 (Phase 3) and US3 (Phase 4) are both P1 and can proceed in parallel once Phase 2 is done, though US3's tests are more meaningful once US1's route conversions (T011–T014) exist to test against.
  - US2 (Phase 5) can start once Foundational is done; T022 extends T005 so should follow it, but T020/T021/T023–T025 have no dependency on US1/US3 being finished.
  - US4 (Phase 6) is fully independent of US1/US2/US3 (different routes, same shared `resolveSsrContext()`) — can proceed any time after Foundational.
- **Polish (Phase 7)**: Depends on all desired user stories being complete.

### Within Each User Story

- Tests can be written alongside or after implementation tasks in this feature (constitution requires tests exist, not strict TDD ordering) — but Playwright tests in each story naturally validate that story's implementation tasks, so implementation tasks are listed first per story here for readability; execute in whichever order suits your workflow.
- `fetchXSSR` implementations before their route's `page.tsx` conversion before their route's content-component prop-seeding.

### Parallel Opportunities

- T001, T002, T003 (Setup) — different files, fully parallel.
- T008 (Foundational unit tests) can start as soon as T004–T007 land.
- T009/T010 (US1), T017/T018 (US3 tests), T020/T021 (US2 cookie writes), T026/T027 (US4 fetch helpers) are each `[P]` — different files/functions, safe to parallelize within their phase.
- US4's entire phase can run in parallel with US1/US2/US3 by a different contributor, since it touches only `/graph` and `/tags`.

---

## Parallel Example: Foundational + User Story 1

```bash
# Setup, fully parallel:
Task: "Create frontend/lib/cookies/constants.ts"
Task: "Create frontend/lib/cookies/set-preference-cookie.ts"
Task: "Create frontend/lib/server/ssr-fetch.ts skeleton"

# Once Foundational (T004-T007) lands, US1's two fetch helpers in parallel:
Task: "Implement fetchArticlesListSSR in frontend/lib/server/ssr-fetch.ts"
Task: "Implement fetchWeeklyReportSSR in frontend/lib/server/ssr-fetch.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (credential/topic/language resolution — CRITICAL, blocks everything).
3. Complete Phase 3: User Story 1 (`/` and `/articles` server-render for authenticated visitors).
4. **STOP and VALIDATE**: run `quickstart.md` steps 1–3 against `frontend_prod`.
5. This alone delivers the bulk of SC-001's LCP improvement, since `/articles` and `/` are the highest-traffic entry points.

### Incremental Delivery

1. Setup + Foundational → shared SSR context resolution ready.
2. US1 → `/` and `/articles` server-render (MVP, P1).
3. US3 → anonymous-visitor paywall preservation proven with dedicated tests (P1, mechanism already shipped in Foundational — no server-side fetch ever attempted for them).
4. US2 → returning-visitor topic/language correctness (P2).
5. US4 → `/graph` and `/tags` join the same pattern (P3).
6. Polish → manual FR-007 degradation check + Lighthouse SC-001 confirmation.

### Parallel Team Strategy

- Developer A: Foundational (Phase 2), then US1 (Phase 3).
- Developer B: US4 (Phase 6) — fully independent routes, can start as soon as Foundational lands.
- Developer C: US2's cookie-write tasks (T020/T021) — independent of route conversions, can start as soon as T001/T002 (Setup) land.
- US3's tests (Phase 4) are best done by whoever finishes US1, since they exercise the same routes.

---

## Notes

- `[P]` tasks touch different files with no unmet dependency — safe to run in parallel.
- `[Story]` label maps each task to its user story for traceability back to spec.md.
- No backend (`backend/`) or scraper (`src/`) tasks — this feature is `frontend/`-only (plan.md Technical Context).
- Every `fetchXSSR` helper MUST go through `resolveSsrContext()` and MUST NOT throw (T007) — a task that adds a new SSR fetch helper without following this pattern is incomplete.
