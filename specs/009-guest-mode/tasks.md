# Tasks: Guest Mode

**Input**: Design documents from `/specs/009-guest-mode/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅

**Scope**: Frontend-only — 1 new provider file, 5 modified files, 2 test files. No backend changes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: i18n keys, GuestModeProvider, and AppProviders wiring — all user stories depend on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T001 [P] Add 4 `guest.*` keys (`continueAsGuest`, `restrictedTitle`, `restrictedMessage`, `graphLimitedPreview`) with English values to `frontend/lib/providers/locales/en.json`
- [x] T002 [P] Add 4 `guest.*` keys with zh-TW values to `frontend/lib/providers/locales/zh-TW.json`
- [x] T003 Create `GuestModeContext` interface, `useGuestMode()` hook, and `GuestModeProvider` component (`sessionStorage`-backed, auto-exit on `status === 'authenticated'`) in `frontend/lib/providers/guest-mode-provider.tsx`
- [x] T004 Wrap `<TopicProvider>` inside `<GuestModeProvider>` in `frontend/lib/providers/index.tsx` (depends T003)

**Checkpoint**: GuestModeProvider available app-wide, i18n keys ready — user story implementation can begin.

---

## Phase 2: User Story 1 - 從登入頁選擇 Guest Mode 並看到真實第一頁文章 (Priority: P1) 🎯 MVP

**Goal**: Users can enter Guest Mode from the login page and see real page-1 articles (not blurred paywall) on the home page, without pagination controls.

**Independent Test**: Visit `/login` → click "Continue as Guest" → home page shows real articles (no blur), no pagination visible; a separate incognito tab visiting `/` without clicking the button still shows blurred paywall.

- [x] T005 [P] [US1] Add "Continue as Guest" ghost/text-link button that calls `enterGuestMode()` then `router.push('/')` below the Google sign-in button in `frontend/app/login/login-page-content.tsx`
- [x] T006 [P] [US1] Replace `isGuest = status === 'unauthenticated'` with `isPaywall = status === 'unauthenticated' && !isGuestMode`; fix article fetch to use `page: isGuestMode ? 1 : page`; conditionally hide pagination controls when `isGuestMode` in `frontend/app/home-page-content.tsx`

**Checkpoint**: Guest Mode entry and home page data display fully functional and independently testable.

---

## Phase 3: User Story 2 - Guest 的頁面存取限制與提示 (Priority: P2)

**Goal**: Guests who navigate to `/settings` via URL see an "Account required" prompt with login/register links instead of settings content.

**Independent Test**: Enter Guest Mode → navigate directly to `/settings` → see "Account required" heading and login/register links (not blank page, not settings content).

- [x] T007 [US2] Add `isGuestMode` check before existing `status` guard at the top of `frontend/app/settings/settings-page-content.tsx`; when `isGuestMode`, render an inline "Account required" prompt using `guest.restrictedTitle` / `guest.restrictedMessage` i18n keys with `<Link href="/login">` and `<Link href="/register">` links

**Checkpoint**: Settings page fully blocked for guests with clear upgrade prompt; existing auth redirect for unauthenticated non-guests unchanged.

---

## Phase 4: User Story 3 - Guest 的知識圖譜（限縮版本）(Priority: P3)

**Goal**: When a guest visits `/graph`, the knowledge graph only shows nodes/edges from the first page of articles, and a banner explains it is a limited preview.

**Independent Test**: Enter Guest Mode → visit `/graph` → node count matches first-page article count (≤20); a `guest.graphLimitedPreview` banner is visible with a login link.

- [x] T008 [P] [US3] Add optional `articleIdFilter?: Set<string>` prop to `KnowledgeGraph` in `frontend/components/features/graph/knowledge-graph.tsx`; when provided, cascade-filter: keep article nodes in set → keep edges between kept nodes → keep tag nodes with remaining article edges → keep group nodes with remaining tag nodes
- [x] T009 [US3] In `frontend/app/graph/page.tsx`: when `isGuestMode`, fetch `GET /articles?page=1&topic_id=<id>` to get first-page article IDs, pass as `articleIdFilter` to `KnowledgeGraph`, and render `guest.graphLimitedPreview` banner with login link (depends T004, T008)

**Checkpoint**: Guest graph is visibly scoped to first-page articles with clear limited-preview indicator.

---

## Phase 5: User Story 4 - 從 Guest Mode 升級為正式帳號 (Priority: P3)

**Goal**: Guests can log in or register at any time; upon login, Guest Mode state clears automatically.

**Note**: US4 requires no additional code tasks — it is fully covered by:
- **T003**: `GuestModeProvider` watches `status === 'authenticated'` and calls `exitGuestMode()` automatically
- **T007**: "Account required" prompt in settings provides login/register links
- **NavBar**: Already shows Login button when `session === null` (confirmed in research.md — no change needed)

**Independent Test**: Enter Guest Mode → visit `/settings` → click login link → log in → verify guest mode cleared (pagination visible, settings accessible).

---

## Phase 6: Polish & Tests

**Purpose**: Tests explicitly required by plan.md; run after all user stories are complete.

- [x] T010 [P] Write Vitest unit tests for `GuestModeContext`: `enterGuestMode` sets sessionStorage, `exitGuestMode` removes it, initial state restored from sessionStorage, auto-exit fires when `status` changes to `'authenticated'` in `frontend/tests/unit/guest-mode-context.test.tsx`
- [x] T011 [P] Write Playwright E2E tests for guest flow: login page shows button, guest home shows real articles without pagination, `/settings` URL shows restricted prompt, `/graph` shows limited nodes with banner, refresh preserves guest state, login clears guest state in `frontend/tests/integration/guest-mode.spec.ts`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: No dependencies — start immediately; T001/T002 can run in parallel; T003 depends on nothing; T004 depends on T003
- **User Story 1 (Phase 2)**: Depends on Foundational complete — T005 and T006 can run in parallel
- **User Story 2 (Phase 3)**: Depends on Foundational complete — can start after Phase 1, parallel with US1
- **User Story 3 (Phase 4)**: Depends on Foundational complete — T008 can start after Phase 1; T009 depends on T008
- **User Story 4 (Phase 5)**: No code tasks — covered by T003 and T007
- **Polish (Phase 6)**: Depends on all user story phases complete — T010 and T011 can run in parallel

### User Story Dependencies

- **US1 (P1)**: After Phase 1. T005 and T006 can run in parallel (different files).
- **US2 (P2)**: After Phase 1. Can start in parallel with US1.
- **US3 (P3)**: After Phase 1. T008 can start in parallel with US1/US2; T009 depends on T008.
- **US4 (P3)**: Zero-effort; inherently resolved by T003 + T007.

### Parallel Opportunities

```bash
# Phase 1 — run in parallel:
Task T001: Add guest i18n keys to en.json
Task T002: Add guest i18n keys to zh-TW.json

# After T003+T004 complete, all stories can start in parallel:
Task T005: Login page "Continue as Guest" button    [US1]
Task T006: Home page isPaywall + isGuestMode refactor [US1]
Task T007: Settings guest guard                      [US2]
Task T008: KnowledgeGraph articleIdFilter prop       [US3]

# Phase 6 — run in parallel:
Task T010: Vitest unit tests for GuestModeContext
Task T011: Playwright E2E tests for guest flow
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Foundational (T001–T004)
2. Complete Phase 2: User Story 1 (T005–T006)
3. **STOP and VALIDATE**: Confirm real articles load for guest, paywall still works for non-guest
4. Demo the core guest onboarding flow

### Incremental Delivery

1. Foundation → Guest Mode entry + home page articles (MVP)
2. Add Settings guard → Guest boundary hardened
3. Add limited graph → Full demo story complete
4. Tests → Production-ready

### Single Developer Sequence

Follow the Implementation Sequence from plan.md:
```
T001/T002 (i18n) → T003 (provider) → T004 (register) →
T005 (login btn) → T006 (home page) → T007 (settings guard) →
T008 (graph filter prop) → T009 (graph page) →
T010/T011 (tests)
```

---

## Notes

- [P] tasks modify different files — no merge conflicts
- Guest Mode is purely frontend; backend is untouched throughout
- The existing paywall path (`isGuest = status === 'unauthenticated'`) MUST still work after T006 — zero regression is SC-002
- `sessionStorage` (not `localStorage`) is intentional — clears on tab close per spec assumption
- Settings layout at `frontend/app/settings/layout.tsx` already exists; guest guard goes in `settings-page-content.tsx` not the layout
- After login, `exitGuestMode()` fires via `useEffect` in T003 — no manual cleanup needed in any other component
