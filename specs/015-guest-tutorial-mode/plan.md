# Implementation Plan: Guest Tutorial Mode

**Branch**: `015-guest-tutorial-mode` | **Date**: 2026-06-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/015-guest-tutorial-mode/spec.md`

## Summary

Add a step-by-step Tutorial Modal (4 steps: Welcome → Articles → Graph → Sign Up CTA) that auto-triggers when a user enters guest mode for the first time in a session. State is managed by extending the existing `GuestModeProvider`; UI uses the existing Shadcn `Dialog` primitive. A `HelpCircle` icon in NavBar lets guests manually reopen the tutorial. No backend changes required.

## Technical Context

**Language/Version**: TypeScript + React 19, Next.js 16 (App Router)

**Primary Dependencies**: Shadcn/UI (Dialog, Button), Radix UI, Tailwind CSS v4, Lucide React, existing `GuestModeProvider` + `I18nProvider`

**Storage**: `sessionStorage` key `guest_tutorial_seen` (string `"true"`) — no DB changes

**Testing**: Vitest (unit) + Playwright (E2E)

**Target Platform**: Web browser (desktop primary, mobile responsive)

**Project Type**: Web application — frontend-only feature

**Performance Goals**: Modal renders <100ms; no new API calls introduced

**Constraints**: Zero new npm packages; must not break existing guest mode tests

**Scale/Scope**: Pure frontend, ~5 files modified/created

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **II. Atomic Frontend Architecture** | ✅ Pass | `TutorialModal` → `components/features/tutorial/` (feature organism); `tutorial-steps.ts` alongside it. Uses `components/ui/dialog.tsx` (atom) correctly |
| **III. (implied) NextAuth / Session** | ✅ Pass | No auth changes; reads `useGuestMode()` which reads `useSession()` internally |
| **VII. (implied) No direct backend calls** | ✅ Pass | No new API calls; tutorial is static content |
| **IX. (implied) No hardcoded env vars** | ✅ N/A | No env vars involved |
| **YAGNI / No speculative features** | ✅ Pass | Exactly what spec requires; no spotlight library, no analytics events beyond scope |
| **i18n consistency** | ✅ Pass | All text via `t()` + locale files; matches existing pattern |

**Post-design re-check**: ✅ All gates still pass. `GuestModeProvider` extension adds 6 fields; still <120 lines total — well within maintainability bounds.

## Project Structure

### Documentation (this feature)

```text
specs/015-guest-tutorial-mode/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── ui-contract.md   # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository root)

```text
frontend/
├── app/
│   └── layout.tsx                          # MODIFY: mount <TutorialModal />
├── components/
│   └── features/
│       ├── navigation/
│       │   └── nav-bar.tsx                 # MODIFY: add HelpCircle icon (guest-only)
│       └── tutorial/                       # NEW directory
│           ├── tutorial-modal.tsx          # NEW: Modal with stepper UI
│           └── tutorial-steps.ts           # NEW: static step definitions
├── lib/
│   └── providers/
│       ├── guest-mode-provider.tsx         # MODIFY: add tutorial state + actions
│       └── locales/
│           ├── en.json                     # MODIFY: add tutorial.* keys
│           └── zh-TW.json                  # MODIFY: add tutorial.* keys (zh-TW)
└── tests/
    ├── unit/
    │   └── tutorial-modal.test.tsx         # NEW: unit tests
    └── integration/
        └── guest-tutorial.spec.ts          # NEW: Playwright E2E
```

**Structure Decision**: Frontend-only, follows existing atomic design. New `components/features/tutorial/` feature directory follows the established pattern (`articles/`, `graph/`, `monitoring/`, etc.).

## Implementation Phases

### Phase A — Core State (GuestModeProvider Extension)

**Files**: `frontend/lib/providers/guest-mode-provider.tsx`

1. Add `isTutorialOpen: boolean` and `tutorialStep: number` to state
2. Implement `openTutorial()`, `closeTutorial()`, `nextTutorialStep()`, `prevTutorialStep()`
3. Modify `enterGuestMode()`: after setting guest mode, check `sessionStorage.getItem('guest_tutorial_seen')`; if absent → set `isTutorialOpen=true, tutorialStep=0`
4. Modify `exitGuestMode()`: reset `isTutorialOpen=false, tutorialStep=0`
5. Export new fields/actions via context

**Guard**: `openTutorial()` is a no-op if `!isGuestMode`.

---

### Phase B — Tutorial Steps Config

**Files**: `frontend/components/features/tutorial/tutorial-steps.ts`

1. Define `TutorialStep` interface
2. Define `TUTORIAL_STEPS` array (4 entries: welcome, articles, graph, cta)
3. Import Lucide icons: `Sparkles`, `Newspaper`, `GitBranch`, `LogIn`

---

### Phase C — TutorialModal Component

**Files**: `frontend/components/features/tutorial/tutorial-modal.tsx`

1. Import `Dialog`, `DialogContent` from `components/ui/dialog`
2. Import `Button` from `components/ui/button`
3. Read state from `useGuestMode()`
4. Render `null` when `!isTutorialOpen`
5. Render `Dialog` (open=`isTutorialOpen`, onOpenChange calls `closeTutorial`)
6. Inside dialog:
   - Dot step indicator: N dots, current step filled
   - Icon (48×48 if present)
   - Title: `t(TUTORIAL_STEPS[tutorialStep].titleKey)`
   - Description: `t(TUTORIAL_STEPS[tutorialStep].descriptionKey)`
   - Navigation row:
     - "Back" button: hidden on step 0, calls `prevTutorialStep()`
     - "Next" button: visible steps 0..N-2, calls `nextTutorialStep()`
     - Last step: "Sign In" → `router.push('/login')` + `closeTutorial()`, "Register" → `router.push('/register')` + `closeTutorial()`
     - "Skip": calls `closeTutorial()` (all steps except last)
     - "X" close: always visible, calls `closeTutorial()`
7. Use `useI18n()` for all text (or however `t()` is exposed in the project)

---

### Phase D — Mount TutorialModal in Layout

**Files**: `frontend/app/layout.tsx` (or the component that wraps inside `GuestModeProvider`)

1. Import `TutorialModal`
2. Add `<TutorialModal />` inside the `GuestModeProvider` scope

---

### Phase E — NavBar HelpCircle Icon

**Files**: `frontend/components/features/navigation/nav-bar.tsx`

1. Import `HelpCircle` from `lucide-react`
2. Import `openTutorial` from `useGuestMode()`
3. Add conditional render: `{isGuestMode && <button onClick={openTutorial}>…<HelpCircle /></button>}`
4. Wrap in `Tooltip` using existing `components/ui/tooltip` pattern
5. Add i18n key `tutorial.reopenLabel` to tooltip content

---

### Phase F — i18n

**Files**: `frontend/lib/providers/locales/en.json`, `zh-TW.json`

Add `tutorial` namespace (see `data-model.md` for full values). Both files must be updated atomically.

---

### Phase G — Tests

**Unit** (`frontend/tests/unit/tutorial-modal.test.tsx`):
- `enterGuestMode()` sets `isTutorialOpen=true` when `guest_tutorial_seen` absent
- `enterGuestMode()` does NOT set `isTutorialOpen=true` when `guest_tutorial_seen='true'`
- `closeTutorial()` sets `isTutorialOpen=false` and writes `guest_tutorial_seen`
- `nextTutorialStep()` increments step, bounded by array length
- `prevTutorialStep()` decrements step, floored at 0
- `openTutorial()` is no-op when not in guest mode
- TutorialModal renders `null` when `isTutorialOpen=false`
- TutorialModal shows correct step content when open

**E2E** (`frontend/tests/integration/guest-tutorial.spec.ts`):
- Tutorial Modal auto-appears after clicking "Continue as Guest"
- "Next" button advances steps, dot indicator updates
- "Skip" closes modal
- Refreshing page in guest mode does NOT reopen tutorial
- Clicking `HelpCircle` in NavBar reopens tutorial
- Last step has "Sign In" and "Register" buttons
- Non-guest users do NOT see the HelpCircle icon
- Existing guest mode E2E tests still pass (regression)

## Complexity Tracking

> No constitution violations.

## Notes

- `useI18n()` hook — verify exact hook name in `lib/providers/i18n-provider.tsx` before implementing Phase C (could be `useTranslation()` or similar)
- `layout.tsx` mounting location — confirm TutorialModal is inside `GuestModeProvider` by checking the provider hierarchy in `lib/providers/index.tsx`
- `Dialog` backdrop click behavior — Radix UI's default is to close on outside click; this maps to `closeTutorial()` via `onOpenChange`
