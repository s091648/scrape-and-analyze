---

description: "Task list for Guest Tutorial Mode implementation"
---

# Tasks: Guest Tutorial Mode

**Input**: Design documents from `specs/015-guest-tutorial-mode/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/ui-contract.md

**Tests**: Included per user story (project constitution §III requires test coverage). Tasks are implementation-first, tests-after within each story (no TDD required — implement directly, tests validate afterward).

**Organization**: Tasks are grouped by user story (from spec.md) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps task to US1/US2/US3/US4 from spec.md
- Every task includes an exact file path

---

## Phase 1: Setup

**Purpose**: Confirm integration points before touching code (no new files/packages needed — zero new npm dependencies per plan.md constraint)

- [ ] T001 [P] Confirm `GuestModeProvider` wraps `LayoutShell`'s render tree by inspecting `frontend/lib/providers/index.tsx`; confirm `frontend/app/layout-shell.tsx` (renders `NavBar`) is the correct mount point for `<TutorialModal />`
- [ ] T002 [P] Confirm the `useI18n()` hook contract (`t`, `locale`, `setLocale`) in `frontend/lib/providers/i18n-provider.tsx` matches usage in `frontend/components/features/navigation/nav-bar.tsx`, for reuse in the new TutorialModal component

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core state and static config that every user story depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 [P] Define `TutorialStep` interface and `TUTORIAL_STEPS` array (4 entries: `welcome`, `articles`, `graph`, `cta` with `Sparkles`, `Newspaper`, `GitBranch`, `LogIn` icons from `lucide-react`) in `frontend/components/features/tutorial/tutorial-steps.ts`
- [ ] T004 [P] Add `tutorial.*` i18n keys (English) — `stepOf`, `skip`, `back`, `next`, `getStarted`, `signIn`, `register`, `reopenLabel`, `step1.title`/`description` through `step4.title`/`description` — to `frontend/lib/providers/locales/en.json` per data-model.md
- [ ] T005 Extend `GuestModeContextType` and `GuestModeProvider` in `frontend/lib/providers/guest-mode-provider.tsx`:
  - Add `isTutorialOpen: boolean` and `tutorialStep: number` state
  - Implement `openTutorial()`, `closeTutorial()`, `nextTutorialStep()` (bounded by `TUTORIAL_STEPS.length - 1`), `prevTutorialStep()` (floored at 0)
  - Modify `enterGuestMode()` to unconditionally set `isTutorialOpen=true, tutorialStep=0` (no storage check)
  - Modify `exitGuestMode()` to reset `isTutorialOpen=false, tutorialStep=0`
  - Guard `openTutorial()` as a no-op when `status === 'unauthenticated' && !isGuestMode`
  - Export all new fields/actions through the context value
  (depends on T003 for the step-count bound)

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - 首次進入 Guest Mode 自動顯示教學引導 (Priority: P1) 🎯 MVP

**Goal**: Entering guest mode automatically opens a step-by-step Tutorial Modal that the user can navigate or dismiss

**Independent Test**: Go to `/login` → click "Continue as Guest" → Tutorial Modal appears automatically showing step 1 (Welcome)

### Implementation for User Story 1

- [ ] T006 [US1] Build `frontend/components/features/tutorial/tutorial-modal.tsx`: import `Dialog`/`DialogContent` from `components/ui/dialog`, render `null` when `!isTutorialOpen`, render dot step indicator, icon (48×48), title/description via `t()`, and Back/Next/Skip/X controls wired to `useGuestMode()` actions (depends on T003, T004, T005)
- [ ] T007 [US1] Add last-step CTA buttons to `frontend/components/features/tutorial/tutorial-modal.tsx`: "Sign In" (`router.push('/login')`) and "Register" (`router.push('/register')`), both calling `closeTutorial()` (depends on T006)
- [ ] T008 [US1] Mount `<TutorialModal />` inside `frontend/app/layout-shell.tsx` alongside `<NavBar />` (depends on T006)

### Tests for User Story 1

- [ ] T009 [P] [US1] Add unit tests to `frontend/tests/unit/guest-mode-context.test.tsx`: `enterGuestMode()` sets `isTutorialOpen=true` and `tutorialStep=0`; `exitGuestMode()` resets `isTutorialOpen=false`; `nextTutorialStep()`/`prevTutorialStep()` respect bounds
- [ ] T010 [P] [US1] Create `frontend/tests/unit/tutorial-modal.test.tsx`: renders `null` when `isTutorialOpen=false`; renders step 0 content when open; Next/Back transitions update the visible step
- [ ] T011 [US1] Create `frontend/tests/integration/guest-tutorial.spec.ts`: Tutorial Modal auto-appears after clicking "Continue as Guest"; "Next" advances steps and updates the dot indicator; "Skip" closes the modal; last step shows working "Sign In"/"Register" navigation

**Checkpoint**: User Story 1 is fully functional and independently testable (MVP)

---

## Phase 4: User Story 2 - 使用者可手動重新開啟教學引導 (Priority: P2)

**Goal**: Guests and members can reopen the Tutorial Modal at any time via a NavBar entry point

**Independent Test**: In guest mode, close the tutorial → click the NavBar "?" icon → Tutorial Modal reopens from step 1

### Implementation for User Story 2

- [ ] T012 [US2] Add a guest/member-only `HelpCircle` icon button to the right-side icon group in `frontend/components/features/navigation/nav-bar.tsx`, calling `openTutorial()` from `useGuestMode()`, wrapped in the existing `Tooltip` primitive with `t('tutorial.reopenLabel')` (depends on T005, T004)

### Tests for User Story 2

- [ ] T013 [P] [US2] Add a unit test in `frontend/tests/unit/tutorial-modal.test.tsx` verifying `openTutorial()` reopens the modal at `tutorialStep=0` and is a no-op when not in guest mode and unauthenticated
- [ ] T014 [US2] Extend `frontend/tests/integration/guest-tutorial.spec.ts`: clicking the `HelpCircle` icon reopens the tutorial from step 1 in guest mode; the icon is hidden for pure unauthenticated (paywall) users; the icon is visible for authenticated members

**Checkpoint**: User Stories 1 AND 2 both work independently

---

## Phase 5: User Story 3 - Tutorial 步驟涵蓋核心功能頁 (Priority: P2)

**Goal**: The 4 tutorial steps clearly and completely cover Welcome, Articles, Graph, and the Sign Up/Login CTA

**Independent Test**: Open the tutorial → step through all 4 steps → confirm each maps to a concrete guest-accessible feature and the final step has Sign In/Register CTAs

### Implementation for User Story 3

- [ ] T015 [US3] Add "Step {{current}} of {{total}}" progress text (`tutorial.stepOf`) alongside the dot indicator in `frontend/components/features/tutorial/tutorial-modal.tsx`

### Tests for User Story 3

- [ ] T016 [P] [US3] Add a unit test in `frontend/tests/unit/tutorial-modal.test.tsx` asserting the 4 steps render in order (welcome → articles → graph → cta), the "Back" control is hidden on step 0, and "Step X of 4" text is correct per step
- [ ] T017 [US3] Extend `frontend/tests/integration/guest-tutorial.spec.ts` verifying all 4 steps appear in the correct order with matching titles and the final step shows both CTA buttons

**Checkpoint**: User Stories 1, 2, and 3 all work independently

---

## Phase 6: User Story 4 - 多語系支援 (Priority: P3)

**Goal**: Tutorial content is fully translated and switches live with the app's locale setting

**Independent Test**: Switch language to zh-TW → enter guest mode → Tutorial Modal displays all steps in Traditional Chinese

### Implementation for User Story 4

- [ ] T018 [P] [US4] Add `tutorial.*` i18n keys (zh-TW translations mirroring T004) to `frontend/lib/providers/locales/zh-TW.json` per data-model.md

### Tests for User Story 4

- [ ] T019 [P] [US4] Add a unit test in `frontend/tests/unit/tutorial-modal.test.tsx` verifying the modal renders zh-TW copy when `locale='zh-TW'` and English copy when `locale='en'`
- [ ] T020 [US4] Extend `frontend/tests/integration/guest-tutorial.spec.ts` verifying tutorial content displays correctly in zh-TW when the app locale is set to zh-TW

**Checkpoint**: All 4 user stories are independently functional

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Regression safety and non-functional requirements (SC-003, SC-004, mobile edge case)

- [ ] T021 [P] Run `cd frontend && npm run test` to confirm `frontend/tests/unit/guest-mode-context.test.tsx` and all other existing unit tests still pass (no regressions)
- [ ] T022 [P] Run `cd frontend && npm run test:e2e` to confirm `frontend/tests/integration/guest-mode.spec.ts` and all other existing E2E specs still pass (no regressions)
- [ ] T023 [P] Run `cd frontend && npm run lint` and `npm run format` on all new/modified tutorial files
- [ ] T024 Manually verify keyboard accessibility (Tab order, Enter triggers buttons, Escape closes) on `TutorialModal` per SC-003
- [ ] T025 Manually verify `TutorialModal` responsive layout at narrow mobile viewport widths per spec.md Edge Cases (no overflow, scrolls if needed)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only — MVP
- **User Story 2 (Phase 4)**: Depends on Foundational only (independent of US1, but naturally follows since HelpCircle reuses the modal built in US1)
- **User Story 3 (Phase 5)**: Depends on Foundational + US1's `tutorial-modal.tsx` existing (adds the progress label to it)
- **User Story 4 (Phase 6)**: Depends on Foundational only (adds zh-TW translations; works once US1 renders any content)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: No dependencies on other stories — deliverable as MVP alone
- **US2 (P2)**: Reuses the `TutorialModal` and `GuestModeProvider` actions from Foundational/US1 but is independently testable (icon click → reopen)
- **US3 (P2)**: Adds to the same `tutorial-modal.tsx` file as US1; independently testable via step-order/content assertions
- **US4 (P3)**: Additive i18n-only change; independently testable via locale switch

### Parallel Opportunities

- T001, T002 (Setup) in parallel
- T003, T004 (Foundational) in parallel; T005 depends on T003
- T009, T010 (US1 tests) in parallel with each other, after T006-T008
- T013 (US2 test) in parallel with T012's dependents
- T016 (US3 test) in parallel
- T018, T019 (US4) in parallel
- T021, T022, T023 (Polish) in parallel

---

## Parallel Example: Foundational Phase

```bash
Task: "Define TutorialStep interface and TUTORIAL_STEPS array in frontend/components/features/tutorial/tutorial-steps.ts"
Task: "Add tutorial.* i18n keys (English) to frontend/lib/providers/locales/en.json"
```

## Parallel Example: User Story 1 Tests

```bash
Task: "Add unit tests to frontend/tests/unit/guest-mode-context.test.tsx for tutorial state transitions"
Task: "Create frontend/tests/unit/tutorial-modal.test.tsx for TutorialModal rendering"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Manually enter guest mode and confirm the tutorial appears and navigates correctly
5. Demo if ready — this alone satisfies FR-001 through FR-007

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → test independently → MVP demo
3. US2 → test independently → manual reopen entry point live
4. US3 → test independently → step content/progress polish
5. US4 → test independently → zh-TW support live
6. Polish → full regression pass + accessibility/mobile checks

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Zero new npm packages — reuses `components/ui/dialog.tsx`, `components/ui/tooltip.tsx`, `lucide-react` (already a dependency)
- No backend changes; no database migrations
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently
