# Data Model: Guest Tutorial Mode & Feature Spotlight

**Feature**: 015-guest-tutorial-mode
**Date**: 2026-06-29
**Updated**: 2026-07-04

---

## Entities

### TutorialStep (Static Config — not persisted to DB)

```typescript
// frontend/components/features/tutorial/tutorial-registry.ts

interface TutorialStep {
  id: string               // Unique step ID within its tour (e.g., "welcome", "articles")
  titleKey: string         // i18n key for step title
  descriptionKey: string   // i18n key for step description
  icon?: LucideIcon        // Optional Lucide icon component (used in centered-card mode)
  targetId?: string        // DOM id of the element to highlight; undefined = centered card, no highlight
  route: string            // Page path this step belongs to; navigated to on step activation if not already there
}
```

### TutorialTour (Static Config — not persisted to DB)

```typescript
interface TutorialTour {
  id: string                        // Unique tour id (e.g., "guest-onboarding", "feature-chat-2026-07")
  kind: "onboarding" | "spotlight"
  steps: TutorialStep[]             // "spotlight" tours: all steps MUST share the same route
}

const TUTORIAL_TOURS: TutorialTour[] = [
  {
    id: "guest-onboarding",
    kind: "onboarding",
    steps: [
      { id: "welcome",  route: "/",         titleKey: "tutorial.step1.title", descriptionKey: "tutorial.step1.description", icon: Sparkles },
      { id: "articles", route: "/articles", titleKey: "tutorial.step2.title", descriptionKey: "tutorial.step2.description", icon: Newspaper, targetId: "tutorial-target-articles" },
      { id: "graph",    route: "/graph",    titleKey: "tutorial.step3.title", descriptionKey: "tutorial.step3.description", icon: GitBranch, targetId: "tutorial-target-graph" },
      { id: "cta",      route: "/",         titleKey: "tutorial.step4.title", descriptionKey: "tutorial.step4.description", icon: LogIn, targetId: "tutorial-target-login" },
    ],
  },
  // Future Feature Spotlight tours are appended here, e.g.:
  // { id: "feature-chat-2026-07", kind: "spotlight", steps: [{ id: "chat", route: "/articles", targetId: "tutorial-target-chat", titleKey: "...", descriptionKey: "..." }] }
]
```

### TutorialState (Runtime — in `TutorialProvider`, NOT `GuestModeProvider`)

```typescript
// frontend/lib/providers/tutorial-provider.tsx

interface TutorialState {
  isTutorialOpen: boolean     // Whether the overlay/card is currently visible
  activeTourId: string | null // Which TutorialTour is currently active
  tutorialStep: number        // Current step index within the active tour's steps (0-based)
}
```

`GuestModeProvider` no longer holds any tutorial fields — it returns to `{ isGuestMode, enterGuestMode, exitGuestMode }` only, matching its pre-015 scope.

---

## Storage Schema

### SessionStorage (existing, unchanged)

| Key | Type | Value | Lifetime |
|-----|------|-------|----------|
| `guest_mode` | string | `"true"` | Session (tab) — existing key, not modified |

### LocalStorage

| Key | Type | Value | Lifetime | Used by |
|-----|------|-------|----------|---------|
| `tutorial_seen_tours` | string | JSON `string[]` e.g. `'["feature-chat-2026-07"]'` | Persistent | Feature Spotlight "seen" tracking |

**Why this key replaces the previously-planned `tutorial_seen_pages`**: the original 015 design reserved `tutorial_seen_pages` for a hypothetical future per-page tutorial. That future arrived as Feature Spotlight tours (per-tour, not strictly per-page — a page could host multiple spotlight tours over time), so the key is renamed/repurposed to store tour ids rather than page ids.

**Auto-trigger rules**:

| Role | Guest Onboarding Tour | Feature Spotlight Tour |
|------|------------------------|--------------------------|
| 純未登入（paywall） | ❌ Never | ❌ Never |
| Guest mode | ✅ **Always**, unconditional, on every `enterGuestMode()` | ✅ On first visit to the tour's `route`, if tour id not in `tutorial_seen_tours` |
| Member (authenticated) | ❌ Never auto-shows (HelpCircle only) | ✅ On first visit to the tour's `route`, if tour id not in `tutorial_seen_tours` |

**Write conditions**:
- `tutorial_seen_tours` gets the active tour's id appended when a **spotlight**-kind tour is closed (via completing all steps, Skip, or X) — see FR-018
- Guest Onboarding Tour (`kind: "onboarding"`) never writes to this key — it is intentionally stateless/repeatable per FR-001

**Read conditions**:
- `TutorialProvider`'s route-watching effect reads `tutorial_seen_tours` to decide whether an unvisited spotlight tour should auto-open
- Only one tour may be open at a time (FR-019): the effect is a no-op if `isTutorialOpen` is already `true`

---

## i18n Keys

Unchanged from the original 015 implementation — same `tutorial.*` namespace, same English/zh-TW copy. See `frontend/lib/providers/locales/en.json` / `zh-TW.json` for current values; verify no keys were dropped when `tutorial-steps.ts` is replaced by `tutorial-registry.ts`.

New key to add: `tutorial.reopenLabel` (already present from the original implementation — no change needed).

---

## State Transitions

```
[User clicks "Continue as Guest"]
        │
        ▼
enterGuestMode()  (GuestModeProvider)
        │
        └─ isGuestMode: false → true
                │
                ▼ (TutorialProvider effect watching isGuestMode)
        openTutorial("guest-onboarding")
                │
                └─ ALWAYS → isTutorialOpen=true, activeTourId="guest-onboarding", tutorialStep=0
                            (no tutorial_seen_tours check)

[User navigates to any page]
        │
        ▼ (TutorialProvider effect watching pathname)
   for each kind:"spotlight" tour:
     if tour.steps[0].route === pathname
        && tour.id not in tutorial_seen_tours
        && (isGuestMode || authenticated)
        && !isTutorialOpen
     → openTutorial(tour.id)   (does NOT force-navigate; only fires when already on the route)

[Tour Open — Step N]
        │
        ├─ User clicks "Next" → tutorialStep++
        │       └─ if new step's route !== current pathname → router.push(route)
        ├─ User clicks "Back" → tutorialStep--
        │       └─ same route sync
        ├─ User clicks "Skip", "X", or Escape (spotlight mode)
        │       → isTutorialOpen=false
        │       └─ if activeTour.kind === "spotlight" → tutorial_seen_tours += activeTourId
        ├─ User reaches last step, clicks "Sign In" / "Register"
        │       → isTutorialOpen=false, router.push('/login' | '/register')
        └─ Guest mode exits (user logs in)
                → exitGuestMode() → isTutorialOpen=false (reset), no tutorial_seen_tours write

[Tour Closed — NavBar HelpCircle icon visible for guest OR member]
        │
        └─ User clicks HelpCircle
                → openTutorial()  (defaults to "guest-onboarding")
                → isTutorialOpen=true, activeTourId="guest-onboarding", tutorialStep=0
                → router.push('/') if not already there
```

---

## Component Tree

```
GuestModeProvider (lib/providers/guest-mode-provider.tsx)  ← isGuestMode only
└─ TutorialProvider (lib/providers/tutorial-provider.tsx)  ← tutorial state + auto-trigger lives here
   └─ [rest of provider chain / app]
      └─ NavBar (components/features/navigation/nav-bar.tsx)
      │  ├─ id="tutorial-target-articles" on the Articles Link
      │  ├─ id="tutorial-target-graph" on the Graph Link
      │  ├─ id="tutorial-target-login" on the login Button/Link
      │  └─ HelpCircle icon (guest+member)  ← calls useTutorial().openTutorial()
      └─ TutorialOverlay (components/features/tutorial/tutorial-overlay.tsx)
         ├─ useTutorialTarget(step.targetId)  ← rect or null
         ├─ Spotlight mode (rect !== null):
         │    ├─ full-screen click-blocking div
         │    ├─ box-shadow "hole" div positioned at rect
         │    └─ PopoverAnchor(virtualRef=rect) + PopoverContent (title/description/dots/nav buttons)
         └─ Centered-card mode (rect === null):
              └─ Dialog / DialogContent (same content, no highlight)
```

---

## Files to Create / Modify

### New Files
| File | Purpose |
|------|---------|
| `frontend/components/features/tutorial/tutorial-registry.ts` | `TutorialStep`/`TutorialTour` types + `TUTORIAL_TOURS` |
| `frontend/components/features/tutorial/tutorial-overlay.tsx` | Spotlight + centered-card dual-mode renderer |
| `frontend/components/features/tutorial/use-tutorial-target.ts` | Generic highlight positioning hook |
| `frontend/components/features/tutorial/use-is-mobile.ts` | `<768px` breakpoint hook |
| `frontend/lib/providers/tutorial-provider.tsx` | Tutorial state machine + auto-trigger logic |

### Removed Files
| File | Reason |
|------|--------|
| `frontend/components/features/tutorial/tutorial-modal.tsx` | Replaced by `tutorial-overlay.tsx` |
| `frontend/components/features/tutorial/tutorial-steps.ts` | Replaced by `tutorial-registry.ts` |

### Modified Files
| File | Change |
|------|--------|
| `frontend/lib/providers/guest-mode-provider.tsx` | Remove tutorial state; back to `isGuestMode`/enter/exit only |
| `frontend/lib/providers/index.tsx` | Mount `TutorialProvider`; export `useTutorial` |
| `frontend/components/features/navigation/nav-bar.tsx` | Add 3 `id="tutorial-target-*"` attributes; HelpCircle uses `useTutorial()` |
| `frontend/app/layout-shell.tsx` | Mount `<TutorialOverlay />` instead of `<TutorialModal />` |
| `frontend/lib/providers/locales/en.json` / `zh-TW.json` | No content change; keys carried over from `tutorial-steps.ts` |
| `frontend/vitest.setup.ts` | Add `ResizeObserver` polyfill |

### Test Files
| File | Purpose |
|------|---------|
| `frontend/tests/unit/tutorial-overlay.test.tsx` | Replaces `tutorial-modal.test.tsx` |
| `frontend/tests/unit/tutorial-provider.test.tsx` | Replaces tutorial assertions previously in `guest-mode-context.test.tsx` |
| `frontend/tests/unit/use-tutorial-target.test.ts` | New |
| `frontend/tests/integration/guest-tutorial.spec.ts` | Rewritten for spotlight/navigation/mobile assertions |
