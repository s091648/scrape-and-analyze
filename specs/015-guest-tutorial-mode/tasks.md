---

description: "Task list for Guest Tutorial Mode & Feature Spotlight implementation"
---

# Tasks: Guest Tutorial Mode & Feature Spotlight

**Input**: Design documents from `specs/015-guest-tutorial-mode/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/ui-contract.md

**Tests**: Included per user story (project constitution §III requires test coverage). Tasks are implementation-first, tests-after within each story (no TDD required — implement directly, tests validate afterward).

**Organization**: Tasks are grouped by user story (from spec.md) to enable independent implementation and testing of each story.

**Note**: This supersedes the previous tasks.md (centered-modal design). The centered-modal implementation (`tutorial-modal.tsx`, `tutorial-steps.ts`, tutorial fields on `GuestModeProvider`) is being replaced, not extended — several tasks below start by removing files/fields from that implementation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps task to US1/US2/US3/US4/US5 from spec.md
- Every task includes an exact file path

---

## Phase 1: Setup

**Purpose**: Remove the superseded centered-modal implementation and confirm mount points before rebuilding

- [ ] T001 Delete `frontend/components/features/tutorial/tutorial-modal.tsx` and `frontend/components/features/tutorial/tutorial-steps.ts` (superseded by `tutorial-overlay.tsx` / `tutorial-registry.ts` built in later phases)
- [ ] T002 Delete `frontend/tests/unit/tutorial-modal.test.tsx` (superseded by `tutorial-overlay.test.tsx`)
- [ ] T003 [P] Confirm `TutorialProvider` mount point: inspect `frontend/lib/providers/index.tsx` to confirm current provider order (`GuestModeProvider` is innermost) before nesting `TutorialProvider` inside it
- [ ] T004 [P] Confirm `PopoverAnchor` forwards `virtualRef` to `@radix-ui/react-popper`'s `Anchor` by re-checking `frontend/components/ui/popover.tsx` and the installed `@radix-ui/react-popover` type defs (already verified during design; re-confirm versions haven't drifted)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Provider split, registry data, and the generic positioning hook that every user story depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Strip tutorial state out of `frontend/lib/providers/guest-mode-provider.tsx`: remove `isTutorialOpen`, `tutorialStep`, `openTutorial`, `closeTutorial`, `nextTutorialStep`, `prevTutorialStep` and the `TUTORIAL_STEPS` import; `enterGuestMode()`/`exitGuestMode()` no longer touch tutorial state; context type back to `{ isGuestMode, enterGuestMode, exitGuestMode }`
- [ ] T006 [P] Create `frontend/components/features/tutorial/tutorial-registry.ts`: `TutorialStep` interface (`id`, `titleKey`, `descriptionKey`, `icon?`, `targetId?`, `route`), `TutorialTour` interface (`id`, `kind: "onboarding" | "spotlight"`, `steps`), and `TUTORIAL_TOURS` array with the single `"guest-onboarding"` tour (welcome/articles/graph/cta, `Sparkles`/`Newspaper`/`GitBranch`/`LogIn` icons from `lucide-react`, per `data-model.md`)
- [ ] T007 Create `frontend/lib/providers/tutorial-provider.tsx`: `TutorialProvider` + `useTutorial()` hook; state `isTutorialOpen`, `activeTourId`, `tutorialStep`; actions `openTutorial(tourId?)` (defaults to `"guest-onboarding"`, guarded no-op when `status === 'unauthenticated' && !isGuestMode`), `closeTutorial()` (writes active tour id to `localStorage['tutorial_seen_tours']` only when active tour's `kind === "spotlight"`), `nextTutorialStep()`/`prevTutorialStep()` (bounded by active tour's `steps.length`); internal `useEffect` on `isGuestMode` → `openTutorial("guest-onboarding")` on false→true transition; internal `useEffect` on `[pathname, isGuestMode, status]` using `usePathname()` → auto-open the first unseen `kind:"spotlight"` tour whose `steps[0].route === pathname`, gated by `(isGuestMode || status === 'authenticated') && !isTutorialOpen` (depends on T006 for `TUTORIAL_TOURS`)
- [ ] T008 Mount `TutorialProvider` inside `GuestModeProvider` in `frontend/lib/providers/index.tsx`; export `useTutorial` alongside the existing `useGuestMode` export (depends on T005, T007)
- [ ] T009 [P] Create `frontend/components/features/tutorial/use-tutorial-target.ts`: `useTutorialTarget(targetId?: string): DOMRect | null` — `requestAnimationFrame` polling for up to 3s if the element isn't immediately present, then recalculates on `window resize`, `scroll` (capture phase), and via `ResizeObserver` on the found element; returns `null` when `targetId` is `undefined` or the timeout elapses
- [ ] T010 [P] Create `frontend/components/features/tutorial/use-is-mobile.ts`: `useIsMobile(): boolean`, `window.innerWidth < 768`, updates on `resize`
- [ ] T011 [P] Add a minimal `ResizeObserver` polyfill/mock to `frontend/vitest.setup.ts` (jsdom has no native implementation; required by T009's tests and any component test that renders `TutorialOverlay`)

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - 首次進入 Guest Mode 自動顯示 Spotlight 導覽 (Priority: P1) 🎯 MVP

**Goal**: Entering guest mode automatically starts the Guest Onboarding Tour: dimmed overlay, highlight cutout over the target NavBar element, anchored description card, and automatic page navigation per step

**Independent Test**: Go to `/login` → click "Continue as Guest" → overlay appears showing step 1 (Welcome, centered card, no highlight); clicking "Next" navigates to `/articles` and highlights the Articles NavBar link

### Implementation for User Story 1

- [ ] T012 [US1] Build `frontend/components/features/tutorial/tutorial-overlay.tsx`: resolve active `TutorialTour`/`TutorialStep` from `useTutorial()` + `TUTORIAL_TOURS`; render `null` when `!isTutorialOpen`; `useEffect` on `[tutorialStep, activeTourId]` to `router.push(step.route)` when it differs from `usePathname()`; call `useTutorialTarget(useIsMobile() ? undefined : step.targetId)` (depends on T006, T007, T009, T010)
- [ ] T013 [US1] In `tutorial-overlay.tsx`, implement **spotlight mode** (`rect !== null`): full-screen `fixed inset-0 pointer-events-auto` transparent click-blocking div; a positioned div matching `rect` with `box-shadow: 0 0 0 9999px rgba(0,0,0,0.6)` and rounded corners for the dimmed-with-cutout effect; `PopoverAnchor` with `virtualRef` pointing at `rect` + `PopoverContent` rendering title/description/step dots/nav buttons; manual `keydown` listener for Escape-to-close (depends on T012)
- [ ] T014 [US1] In `tutorial-overlay.tsx`, implement **centered-card mode** (`rect === null`): reuse `Dialog`/`DialogContent` from `components/ui/dialog` for Welcome step, mobile viewport, or 3s target-not-found timeout (depends on T012)
- [ ] T015 [US1] Add `id="tutorial-target-articles"` to the Articles `Link` and `id="tutorial-target-graph"` to the Graph `Link` in `frontend/components/features/navigation/nav-bar.tsx`
- [ ] T016 [US1] Add `id="tutorial-target-login"` to the login `Button`/`Link` in the unauthenticated branch of `frontend/components/features/navigation/nav-bar.tsx` (the CTA step's highlight target)
- [ ] T017 [US1] Add last-step CTA buttons in `tutorial-overlay.tsx`: "Sign In" (`router.push('/login')`) and "Register" (`router.push('/register')`), both calling `closeTutorial()` (depends on T013, T014)
- [ ] T018 [US1] Mount `<TutorialOverlay />` inside `frontend/app/layout-shell.tsx`, replacing the removed `<TutorialModal />` (depends on T013, T014)

### Tests for User Story 1

- [ ] T019 [P] [US1] Create `frontend/tests/unit/tutorial-provider.test.tsx`: `enterGuestMode()` (via `useGuestMode`) triggers `openTutorial("guest-onboarding")` in `TutorialProvider`; `closeTutorial()` does NOT write to `tutorial_seen_tours` for the onboarding tour; `nextTutorialStep()`/`prevTutorialStep()` respect bounds of the active tour
- [ ] T020 [P] [US1] Create `frontend/tests/unit/use-tutorial-target.test.ts`: returns the element's rect once mounted; polls and eventually returns `null` if the target never appears; recalculates on `resize`
- [ ] T021 [P] [US1] Create `frontend/tests/unit/tutorial-overlay.test.tsx`: renders `null` when closed; renders centered card for the Welcome step; renders spotlight mode (mocked `getBoundingClientRect`) for the Articles step; Next/Back transitions update the visible step and call `router.push`
- [ ] T022 [US1] Create `frontend/tests/integration/guest-tutorial.spec.ts`: overlay auto-appears after clicking "Continue as Guest"; "Next" navigates to `/articles` then `/graph` with the highlight box following; "Skip" closes the overlay; last step highlights the login button with working "Sign In"/"Register" navigation

**Checkpoint**: User Story 1 is fully functional and independently testable (MVP)

---

## Phase 4: User Story 2 - 使用者可手動重新開啟 Guest Onboarding Tour (Priority: P2)

**Goal**: Guests and members can reopen the Guest Onboarding Tour at any time via the NavBar HelpCircle entry point

**Independent Test**: In guest mode, close the tour → click the NavBar "?" icon → tour reopens from step 1, navigating back to `/`

### Implementation for User Story 2

- [ ] T023 [US2] Update the `HelpCircle` button in `frontend/components/features/navigation/nav-bar.tsx` to call `openTutorial()` from `useTutorial()` (was `useGuestMode()`); keep the existing `(isGuestMode || !!session)` visibility guard and `Tooltip`/`t('tutorial.reopenLabel')` wiring (depends on T008)

### Tests for User Story 2

- [ ] T024 [P] [US2] Extend `frontend/tests/unit/tutorial-provider.test.tsx`: `openTutorial()` with no argument opens `"guest-onboarding"` at step 0; is a no-op when not in guest mode and unauthenticated
- [ ] T025 [P] [US2] Extend `frontend/tests/unit/nav-bar.test.tsx`: HelpCircle calls `useTutorial().openTutorial`; hidden for pure unauthenticated (paywall) users; visible for authenticated members
- [ ] T026 [US2] Extend `frontend/tests/integration/guest-tutorial.spec.ts`: clicking `HelpCircle` reopens the tour from step 1 (navigating back to `/` if elsewhere); icon hidden for paywall users, visible for authenticated members

**Checkpoint**: User Stories 1 AND 2 both work independently

---

## Phase 5: User Story 3 - Tutorial 步驟精準 Highlight 核心功能頁 (Priority: P2)

**Goal**: The 4 Guest Onboarding steps clearly cover Welcome, Articles, Graph, and the Sign Up/Login CTA, each highlighting the correct concrete UI element, with graceful fallback when a target can't be found

**Independent Test**: Open the tour → step through all 4 steps → confirm each highlights the correct NavBar element and navigates to the correct route; simulate a missing target and confirm fallback to centered card after 3s

### Implementation for User Story 3

- [ ] T027 [US3] Add "Step {current} of {total}" progress text (`tutorial.stepOf`) alongside the dot indicator in both spotlight and centered-card branches of `tutorial-overlay.tsx` (single-brace `{current}`/`{total}` placeholders, matching the actual `t()` implementation)
- [ ] T028 [US3] Verify/adjust the 3s timeout fallback in `use-tutorial-target.ts` is wired so `tutorial-overlay.tsx` renders centered-card mode once the hook settles on `null` (no spinner/blocking state in between)

### Tests for User Story 3

- [ ] T029 [P] [US3] Extend `frontend/tests/unit/tutorial-overlay.test.tsx`: all 4 steps render in order (welcome → articles → graph → cta) with correct `targetId`/`route` per step; "Back" hidden on step 0; "Step X of 4" text correct per step; a step with a permanently-missing target falls back to centered card
- [ ] T030 [US3] Extend `frontend/tests/integration/guest-tutorial.spec.ts`: all 4 steps appear in the correct order with matching titles/highlight targets; final step shows both CTA buttons

**Checkpoint**: User Stories 1, 2, and 3 all work independently

---

## Phase 6: User Story 4 - 多語系支援 (Priority: P3)

**Goal**: Tutorial content is fully translated and switches live with the app's locale setting

**Independent Test**: Switch language to zh-TW → enter guest mode → tour displays all steps in Traditional Chinese

### Implementation for User Story 4

- [ ] T031 [P] [US4] Verify all `tutorial.*` keys survive the `tutorial-steps.ts` → `tutorial-registry.ts` migration in `frontend/lib/providers/locales/en.json` (no content changes expected — same keys as the original 015 implementation)
- [ ] T032 [P] [US4] Verify all `tutorial.*` keys survive the migration in `frontend/lib/providers/locales/zh-TW.json` (no content changes expected)

### Tests for User Story 4

- [ ] T033 [P] [US4] Extend `frontend/tests/unit/tutorial-overlay.test.tsx`: renders zh-TW copy when `locale='zh-TW'` and English copy when `locale='en'`, in both spotlight and centered-card modes
- [ ] T034 [US4] Extend `frontend/tests/integration/guest-tutorial.spec.ts`: tutorial content displays correctly in zh-TW when the app locale is zh-TW

**Checkpoint**: All 4 original user stories are independently functional

---

## Phase 7: User Story 5 - Feature Spotlight Tour 機制（新功能對所有使用者自動導覽） (Priority: P2)

**Goal**: A generic, registry-driven mechanism so that a `kind: "spotlight"` tour auto-opens for guest/member users the first time they visit its target page, and is never shown again once dismissed — without forcing navigation away from the user's current page

**Independent Test**: Register a test-only `kind: "spotlight"` tour targeting `/articles` in the registry → visit `/articles` as a user who hasn't seen it → overlay auto-opens → close it → reload `/articles` → overlay does not reopen

### Implementation for User Story 5

- [ ] T035 [US5] Verify the spotlight auto-trigger effect in `frontend/lib/providers/tutorial-provider.tsx` (built in T007) correctly reads `localStorage['tutorial_seen_tours']`, filters `TUTORIAL_TOURS` for `kind === "spotlight"`, and only opens when `steps[0].route === pathname` (no cross-page forced navigation for this kind)
- [ ] T036 [US5] Verify `closeTutorial()` in `tutorial-provider.tsx` appends `activeTourId` to `localStorage['tutorial_seen_tours']` only when the active tour's `kind === "spotlight"` (onboarding tours must remain unaffected, per FR-001)
- [ ] T037 [US5] Verify mutual exclusion: the spotlight auto-trigger effect checks `!isTutorialOpen` so it cannot interrupt an in-progress Guest Onboarding Tour (FR-019)

### Tests for User Story 5

- [ ] T038 [P] [US5] Extend `frontend/tests/unit/tutorial-provider.test.tsx` with a fixture spotlight tour (test-only entry, not added to the real `TUTORIAL_TOURS`, injected via module mock): auto-opens on matching route + unseen + guest/member role; does not auto-open for paywall users; does not auto-open when `isTutorialOpen` is already `true`; writes to `tutorial_seen_tours` on close; does not reopen once seen
- [ ] T039 [US5] Extend `frontend/tests/integration/guest-tutorial.spec.ts` (or a new `feature-spotlight.spec.ts`) with a fixture spotlight tour: auto-opens on first visit to its route without navigating away from that route; does not reopen after the tour is closed and the page is reloaded; not shown to paywall (pure unauthenticated) users

**Checkpoint**: All 5 user stories are independently functional; the registry is ready for a real Feature Spotlight tour (e.g. chat) to be added later as a pure data change

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Regression safety and non-functional requirements (SC-003, SC-004, SC-006, mobile edge case)

- [ ] T040 [P] Run `docker compose exec frontend npm run test` — confirm all unit tests pass, including the newly rewritten tutorial suite, with no regressions in unrelated files (per project convention, tests run inside Docker, not on host)
- [ ] T041 [P] Run `docker compose exec frontend npm run test:e2e` — confirm `guest-tutorial.spec.ts` and all other existing E2E specs still pass (no regressions)
- [ ] T042 [P] Run lint/format **only on the new/modified tutorial files** (not the whole repo) — e.g. `docker compose exec frontend npx eslint components/features/tutorial lib/providers/tutorial-provider.tsx lib/providers/guest-mode-provider.tsx components/features/navigation/nav-bar.tsx app/layout-shell.tsx tests/unit/tutorial-*.test.tsx tests/unit/use-tutorial-target.test.ts tests/integration/guest-tutorial.spec.ts` and the equivalent scoped `prettier --write` — do NOT run an unscoped `npm run format` (reformats the entire repo)
- [ ] T043 Manually verify keyboard accessibility (Tab order, Enter triggers buttons, Escape closes) on `TutorialOverlay` in both spotlight and centered-card modes per SC-003
- [ ] T044 Manually verify `TutorialOverlay` at narrow mobile viewport widths (< 768px) falls back to centered card for every step, with no overflow, per FR-016
- [ ] T045 Manually verify highlight box position tracks the target element within ~2px after a window resize and after scrolling a page with a non-fixed target, per SC-006

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only — MVP
- **User Story 2 (Phase 4)**: Depends on Foundational only (independent of US1, but naturally follows since HelpCircle reuses the overlay built in US1)
- **User Story 3 (Phase 5)**: Depends on Foundational + US1's `tutorial-overlay.tsx` existing (adds progress label + fallback polish to it)
- **User Story 4 (Phase 6)**: Depends on Foundational only (verifies i18n; works once US1 renders any content)
- **User Story 5 (Phase 7)**: Depends on Foundational (the spotlight trigger logic was built as part of T007) + US1's `tutorial-overlay.tsx` for rendering — mostly verification + tests for logic already implemented in Phase 2
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: No dependencies on other stories — deliverable as MVP alone
- **US2 (P2)**: Reuses the `TutorialOverlay`/`TutorialProvider` from Foundational/US1 but is independently testable (icon click → reopen)
- **US3 (P2)**: Adds to the same `tutorial-overlay.tsx` file as US1; independently testable via step-order/content/fallback assertions
- **US4 (P3)**: Additive i18n verification; independently testable via locale switch
- **US5 (P2)**: Exercises the spotlight trigger logic already present in `TutorialProvider` (Phase 2); independently testable with a fixture tour, no dependency on the real onboarding tour content

### Parallel Opportunities

- T003, T004 (Setup) in parallel
- T006, T009, T010, T011 (Foundational) in parallel; T007 depends on T006, T008 depends on T005+T007
- T019, T020, T021 (US1 tests) in parallel with each other, after T012-T018
- T024, T025 (US2 tests) in parallel
- T029 (US3 test) in parallel
- T031, T032 (US4 i18n verification) in parallel; T033 after both
- T038 (US5 test) in parallel with US5 verification tasks
- T040, T041, T042 (Polish) in parallel

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (remove superseded files)
2. Complete Phase 2: Foundational (provider split, registry, positioning hooks — blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Manually enter guest mode and confirm the spotlight tour appears, navigates pages, and highlights the correct elements
5. Demo if ready — this alone satisfies FR-001 through FR-007, FR-013 through FR-016

### Incremental Delivery

1. Setup + Foundational → foundation ready (provider split + registry + hooks)
2. US1 → test independently → MVP demo (spotlight tour working end-to-end)
3. US2 → test independently → manual reopen entry point live
4. US3 → test independently → step content/progress/fallback polish
5. US4 → test independently → zh-TW support live
6. US5 → test independently → generic Feature Spotlight mechanism live (ready for a real spotlight tour's content to be added later as pure data)
7. Polish → full regression pass + accessibility/mobile/positioning-accuracy checks

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Zero new npm packages — reuses `components/ui/dialog.tsx`, `components/ui/popover.tsx` (+ its `virtualRef` support from `@radix-ui/react-popper`), `components/ui/tooltip.tsx`, `lucide-react` (already dependencies)
- No backend changes; no database migrations; all "seen" state is `localStorage`-only (see plan.md "Why localStorage, not DB")
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently
- **Do not run an unscoped `npm run format` / `npm run lint --fix` across the whole repo** — a prior session run of `npm run format` on the whole project produced ~230 unrelated file diffs that had to be reverted; always scope format/lint commands to the files touched by this feature (see T042)
