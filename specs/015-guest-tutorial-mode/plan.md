# Implementation Plan: Guest Tutorial Mode & Feature Spotlight

**Branch**: `015-guest-tutorial-mode` | **Date**: 2026-06-29 | **Updated**: 2026-07-04 | **Spec**: [spec.md](./spec.md)

## Summary

Replace the centered-modal Tutorial with a **spotlight/highlight tour**: a dimmed overlay with a cutout over the target UI element, a description card anchored next to it, and automatic page navigation to the step's route. Two kinds of tours share this UI:

- **Guest Onboarding Tour** (`kind: "onboarding"`) — 4 steps (Welcome → Articles → Graph → Sign Up CTA), auto-starts unconditionally every time a user enters guest mode, can force-navigate across pages.
- **Feature Spotlight Tour** (`kind: "spotlight"`) — auto-starts for guest/member users the first time they visit the tour's target page, if not already marked seen in `localStorage`. Never force-navigates. Scoped to a single route.

Tutorial state moves out of `GuestModeProvider` into a new `TutorialProvider` (tutorial concerns now apply to all users, not just guests). Highlight positioning is implemented with a generic `useTutorialTarget` hook (no third-party tour library) and the description card is anchored via the existing `components/ui/popover.tsx` (`PopoverAnchor` + Radix's `virtualRef`). No backend changes; all "seen" state lives in `localStorage`.

## Technical Context

**Language/Version**: TypeScript + React 19, Next.js 16 (App Router)

**Primary Dependencies**: Shadcn/UI (Popover, Dialog for the centered-card fallback, Button), Radix UI (`@radix-ui/react-popper` `virtualRef` for anchoring to an arbitrary rect), Tailwind CSS v4, Lucide React, `next/navigation` (`usePathname`, `useRouter`)

**Storage**: `localStorage` key `tutorial_seen_tours` (JSON `string[]` of seen Feature Spotlight tour ids); Guest Onboarding auto-trigger remains unconditional/role-based, not storage-gated. No DB changes — see "Why localStorage, not DB" below.

**Testing**: Vitest (unit, incl. a `ResizeObserver` polyfill in `vitest.setup.ts`) + Playwright (E2E)

**Target Platform**: Web browser (desktop: full spotlight tour; mobile < 768px: centered-card fallback only)

**Project Type**: Web application — frontend-only feature

**Performance Goals**: Overlay renders <100ms after target found; highlight position recalculates within one animation frame of resize/scroll; no new API calls introduced

**Constraints**: Zero new npm packages; must not break existing guest mode tests; highlight targets must not be clickable during a tour

**Scale/Scope**: Pure frontend, ~10 files modified/created

### Why localStorage, not DB, for "seen" state

Considered storing per-user seen-tour state in the backend (new `User` column/table + API endpoint) so it would sync across a member's devices. Rejected:
- Guest users have no account — their state can only ever live client-side, so a DB path can't cover the guest case anyway.
- The codebase already has this exact pattern for members: `ReleaseNotesPopover` (`frontend/components/features/navigation/release-notes-popover.tsx`) tracks `last_seen_release_version` in `localStorage` for all users, no backend involved.
- Worst case of a localStorage-only approach is a member seeing a spotlight tour again after switching browsers/devices — low-stakes, not worth a migration + endpoint + schema change.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **II. Atomic Frontend Architecture** | ✅ Pass | `TutorialOverlay` → `components/features/tutorial/` (feature organism); reuses `components/ui/popover.tsx` (atom) for anchored positioning instead of introducing a new positioning primitive |
| **III. (implied) NextAuth / Session** | ✅ Pass | No auth changes; `TutorialProvider` reads `useSession()` / `useGuestMode()` internally |
| **VII. (implied) No direct backend calls** | ✅ Pass | No new API calls; tutorial content and seen-state are static/localStorage only |
| **IX. (implied) No hardcoded env vars** | ✅ N/A | No env vars involved |
| **YAGNI / No speculative features** | ✅ Pass | The generic `useTutorialTarget` hook (scroll/resize/async-mount handling) is justified by an explicitly stated near-term need (chat feature spotlight), not speculative; no spotlight library added |
| **i18n consistency** | ✅ Pass | All text via `t()` + locale files; matches existing pattern |

**Post-design re-check**: ✅ All gates still pass. Splitting `GuestModeProvider` (now `isGuestMode`/enter/exit only) from the new `TutorialProvider` restores single-responsibility now that tutorials serve all users, not just guests.

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
└── tasks.md              # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository root)

```text
frontend/
├── app/
│   └── layout-shell.tsx                    # MODIFY: mount <TutorialOverlay /> (was <TutorialModal />)
├── components/
│   └── features/
│       ├── navigation/
│       │   └── nav-bar.tsx                 # MODIFY: HelpCircle calls useTutorial(); add id="tutorial-target-*" on Articles/Graph links + login button
│       └── tutorial/
│           ├── tutorial-registry.ts        # NEW (replaces tutorial-steps.ts): TutorialStep + TutorialTour types, TUTORIAL_TOURS[]
│           ├── tutorial-overlay.tsx        # NEW (replaces tutorial-modal.tsx): spotlight + centered-card dual-mode renderer
│           ├── use-tutorial-target.ts      # NEW: generic highlight positioning hook
│           └── use-is-mobile.ts            # NEW: <768px breakpoint hook
├── lib/
│   └── providers/
│       ├── guest-mode-provider.tsx         # MODIFY: strip tutorial state back out; isGuestMode/enter/exit only
│       ├── tutorial-provider.tsx           # NEW: tutorial state machine + auto-trigger logic for both tour kinds
│       ├── index.tsx                       # MODIFY: mount TutorialProvider inside GuestModeProvider; export useTutorial
│       └── locales/
│           ├── en.json                     # MODIFY: tutorial.* keys (unchanged content, same keys)
│           └── zh-TW.json                  # MODIFY: tutorial.* keys (zh-TW)
└── tests/
    ├── unit/
    │   ├── tutorial-overlay.test.tsx       # NEW (replaces tutorial-modal.test.tsx)
    │   ├── tutorial-provider.test.tsx      # NEW (replaces tutorial assertions in guest-mode-context.test.tsx)
    │   └── use-tutorial-target.test.ts     # NEW
    └── integration/
        └── guest-tutorial.spec.ts          # MODIFY: spotlight-aware assertions, mobile fallback, route navigation
```

**Structure Decision**: Frontend-only, follows existing atomic design. `GuestModeProvider` returns to its pre-015 single responsibility; tutorial orchestration moves to a dedicated `TutorialProvider` since it now serves guests, members, and (indirectly, via visibility rules) is aware of paywall users too.

## Implementation Phases

### Phase A — Provider Split & Tutorial State

**Files**: `frontend/lib/providers/guest-mode-provider.tsx`, `frontend/lib/providers/tutorial-provider.tsx`, `frontend/lib/providers/index.tsx`

1. Strip `isTutorialOpen`/`tutorialStep`/tutorial actions out of `GuestModeProvider`; it goes back to `{ isGuestMode, enterGuestMode, exitGuestMode }`
2. New `TutorialProvider`: `isTutorialOpen`, `activeTourId`, `tutorialStep`, `openTutorial(tourId?)`, `closeTutorial()`, `nextTutorialStep()`, `prevTutorialStep()`
3. `useEffect` on `isGuestMode` transitioning to `true` → `openTutorial("guest-onboarding")` unconditionally
4. `useEffect` on `[pathname, isGuestMode, status]` → for each `kind: "spotlight"` tour in the registry: if `tour.steps[0].route === pathname && !seenTourIds.includes(tour.id) && (isGuestMode || status === "authenticated") && !isTutorialOpen` → `openTutorial(tour.id)`
5. `closeTutorial()`: if the active tour's `kind === "spotlight"`, append its id to `localStorage['tutorial_seen_tours']`
6. `openTutorial()` with no argument defaults to `"guest-onboarding"` (used by NavBar HelpCircle); guarded as a no-op when `status === 'unauthenticated' && !isGuestMode`
7. Mount order in `index.tsx`: `GuestModeProvider > TutorialProvider > children`; export `useTutorial` alongside `useGuestMode`

---

### Phase B — Tutorial Registry

**Files**: `frontend/components/features/tutorial/tutorial-registry.ts`

1. `TutorialStep`: `{ id, titleKey, descriptionKey, icon?, targetId?, route }`
2. `TutorialTour`: `{ id, kind: "onboarding" | "spotlight", steps: TutorialStep[] }`
3. `TUTORIAL_TOURS`: one entry, `"guest-onboarding"` — welcome (`route: "/"`, no `targetId`), articles (`route: "/articles"`, `targetId: "tutorial-target-articles"`), graph (`route: "/graph"`, `targetId: "tutorial-target-graph"`), cta (`route: "/"`, `targetId: "tutorial-target-login"`)
4. Import Lucide icons: `Sparkles`, `Newspaper`, `GitBranch`, `LogIn`
5. Adding a future Feature Spotlight tour = appending one `TutorialTour` entry with `kind: "spotlight"` and all steps sharing one `route`

---

### Phase C — Highlight Positioning

**Files**: `frontend/components/features/tutorial/use-tutorial-target.ts`, `frontend/components/features/tutorial/use-is-mobile.ts`

1. `useTutorialTarget(targetId?: string): DOMRect | null` — polls `document.getElementById` via `requestAnimationFrame` for up to 3s if not immediately found (handles post-navigation async mount); once found, recalculates on `resize`, `scroll` (capture phase, for non-fixed/scrollable ancestor targets), and via `ResizeObserver` on the element itself; returns `null` if never found (caller falls back to centered card)
2. `useIsMobile(): boolean` — `window.innerWidth < 768`, updates on `resize`
3. `vitest.setup.ts`: add a minimal `ResizeObserver` polyfill for jsdom

---

### Phase D — TutorialOverlay Component

**Files**: `frontend/components/features/tutorial/tutorial-overlay.tsx`

1. Read `isTutorialOpen`, `activeTourId`, `tutorialStep` from `useTutorial()`; render `null` when closed
2. Resolve active `TutorialTour` + current `TutorialStep` from `TUTORIAL_TOURS`
3. `useEffect` on `[tutorialStep, activeTourId]`: if `step.route !== pathname`, `router.push(step.route)`
4. `rect = useTutorialTarget(useIsMobile() ? undefined : step.targetId)`
5. **Spotlight mode** (`rect !== null`): full-screen transparent click-blocking div (`pointer-events: auto`) + a div positioned at `rect` with `box-shadow: 0 0 0 9999px rgba(0,0,0,0.6)` for the dimmed-with-cutout effect + `PopoverAnchor virtualRef` anchored description card (title/description/step dots/Back/Next/Skip/X, or Sign In/Register on the last step)
6. **Centered-card mode** (`rect === null` — Welcome step, mobile, or target-not-found timeout): reuses the actual `Dialog`/`DialogContent` primitive (same markup as the pre-redesign `TutorialModal`), which gives Escape-to-close, focus trap, and backdrop-click-to-close for free
7. **Spotlight mode** has no `Dialog` wrapper (custom overlay div, not Radix `Dialog`), so it manually replicates Escape-to-close via a `keydown` listener (`useEffect` while `isTutorialOpen`) and manages initial focus on the description card for keyboard nav (SC-003); there is no backdrop-click-to-close since the click-blocking layer intentionally swallows all clicks
8. All copy via `useI18n()`'s `t()`

---

### Phase E — Mount Point & NavBar

**Files**: `frontend/app/layout-shell.tsx`, `frontend/components/features/navigation/nav-bar.tsx`

1. `layout-shell.tsx`: swap `<TutorialModal />` → `<TutorialOverlay />`
2. `nav-bar.tsx`: add `id="tutorial-target-articles"`, `id="tutorial-target-graph"` on the respective `Link`s; add `id="tutorial-target-login"` on the login `Button`/`Link`
3. HelpCircle button: `onClick={() => openTutorial()}` from `useTutorial()` (was `useGuestMode()`)

---

### Phase F — i18n

**Files**: `frontend/lib/providers/locales/en.json`, `zh-TW.json`

No content changes vs. current `tutorial.*` keys — same keys, same copy (they were written generically enough to still apply). Verify keys survive the `tutorial-steps.ts` → `tutorial-registry.ts` rename with no orphaned/missing keys.

---

### Phase G — Tests

**Unit**:
- `tutorial-provider.test.tsx`: guest-onboarding unconditional trigger; spotlight trigger gated by route + seen-list + role; `tutorial_seen_tours` write on close; paywall users see neither tour; only one tour open at a time
- `use-tutorial-target.test.ts`: returns rect once element found; polls up to 3s then returns `null`; recalculates on resize/scroll/ResizeObserver
- `tutorial-overlay.test.tsx`: spotlight rendering with mocked `getBoundingClientRect`; centered-card fallback (no target / mobile / timeout); route push on step change; highlighted element not clickable
- `nav-bar.test.tsx`: `id="tutorial-target-*"` attributes present; HelpCircle calls `useTutorial().openTutorial()`

**E2E** (`guest-tutorial.spec.ts`):
- Guest Onboarding: overlay + highlight box appear; "Next" navigates to `/articles`/`/graph` and highlight follows; "Back" navigates back; "Skip" closes; last step highlights login button with working Sign In/Register
- Mobile viewport (< 768px): all steps render as centered card, no highlight box
- Regression: existing guest mode E2E specs still pass

## Complexity Tracking

> No constitution violations. Provider split (Phase A) is a scope correction, not added complexity — tutorial state was only ever in `GuestModeProvider` because the original spec was guest-only.

## Notes

- `useI18n()` hook contract unchanged from the original 015 implementation
- Radix's `@radix-ui/react-popper` `Anchor` component supports a `virtualRef: RefObject<{ getBoundingClientRect(): DOMRect }>` prop — verified present in the installed `@radix-ui/react-popover` version; this is what makes the anchored-to-a-rect description card possible without a new dependency
- `Dialog` backdrop click behavior from the original design is dropped — the spotlight overlay's click-blocking layer is a plain div, not a `Dialog`, so closing now happens only via X/Skip/Escape, not backdrop click (there is no dismissable backdrop click target once the overlay covers the whole screen including the highlight)
