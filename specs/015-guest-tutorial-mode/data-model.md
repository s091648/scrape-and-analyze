# Data Model: Guest Tutorial Mode & Feature Spotlight

**Feature**: 015-guest-tutorial-mode
**Date**: 2026-06-29
**Updated**: 2026-07-05 (synced with shipped 10-step registry, real `feature-chat-2026-07` spotlight tour, `isCta`/member-variant fields, and `release-notes-popover.tsx`)

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
  isCta?: boolean          // Marks the sign-up CTA step: renders Sign In/Register/Stay-in-Guest-Mode
                            // instead of Next, regardless of position. Only the guest onboarding
                            // tour's final step sets this. Never rendered when the tour is reopened
                            // by an already-authenticated member (isGuestMode === false) — that
                            // case falls back to a plain "Done" button instead.
  titleKeyMember?: string       // Overrides titleKey when an authenticated member (not a guest)
  descriptionKeyMember?: string // views this step, e.g. reopened via NavBar's HelpCircle.
                                 // Falls back to titleKey/descriptionKey when unset.
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
      { id: "welcome",       route: "/",         titleKey: "tutorial.step1.title",  descriptionKey: "tutorial.step1.description",  titleKeyMember: "tutorial.step1Member.title", descriptionKeyMember: "tutorial.step1Member.description", icon: Sparkles },
      { id: "articles",      route: "/articles", titleKey: "tutorial.step2.title",  descriptionKey: "tutorial.step2.description",  icon: Newspaper, targetId: "tutorial-target-articles" },
      { id: "graph",         route: "/graph",    titleKey: "tutorial.step3.title",  descriptionKey: "tutorial.step3.description",  icon: GitBranch, targetId: "tutorial-target-graph" },
      { id: "tags",          route: "/tags",     titleKey: "tutorial.step4.title",  descriptionKey: "tutorial.step4.description",  icon: Tags,      targetId: "tutorial-target-tags" },
      { id: "language",      route: "/",         titleKey: "tutorial.step5.title",  descriptionKey: "tutorial.step5.description",  icon: Globe,     targetId: "tutorial-target-language" },
      { id: "theme",         route: "/",         titleKey: "tutorial.step6.title",  descriptionKey: "tutorial.step6.description",  icon: SunMoon,   targetId: "tutorial-target-theme" },
      { id: "github",        route: "/",         titleKey: "tutorial.step7.title",  descriptionKey: "tutorial.step7.description",  icon: Github,    targetId: "tutorial-target-github" },
      { id: "docs",          route: "/",         titleKey: "tutorial.step8.title",  descriptionKey: "tutorial.step8.description",  icon: BookOpen,  targetId: "tutorial-target-docs" },
      { id: "release-notes", route: "/",         titleKey: "tutorial.step9.title",  descriptionKey: "tutorial.step9.description",  icon: ScrollText, targetId: "tutorial-target-release-notes" },
      { id: "cta",           route: "/",         titleKey: "tutorial.step10.title", descriptionKey: "tutorial.step10.description", titleKeyMember: "tutorial.step10Member.title", descriptionKeyMember: "tutorial.step10Member.description", icon: LogIn, targetId: "tutorial-target-login", isCta: true },
    ],
  },
  // Real Feature Spotlight tour, added as the first live example of the
  // extensible registry mechanism (see spec.md Assumptions):
  {
    id: "feature-chat-2026-07",
    kind: "spotlight",
    steps: [
      { id: "chat-pin",    route: "/articles", titleKey: "tutorial.chatPin.title",    descriptionKey: "tutorial.chatPin.description",    icon: Sparkles,      targetId: "tutorial-target-chat-pin" },
      { id: "chat-toggle", route: "/articles", titleKey: "tutorial.chatToggle.title", descriptionKey: "tutorial.chatToggle.description", icon: MessageSquare, targetId: "tutorial-target-chat-toggle" },
    ],
  },
  // Additional Feature Spotlight tours are appended the same way — one new
  // TutorialTour entry with kind: "spotlight" and all steps sharing one route.
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

`tutorial.*` namespace, `en.json` / `zh-TW.json`:

- `stepOf`, `skip`, `back`, `next`, `getStarted`, `signIn`, `register`, `stayGuest`, `done`, `reopenLabel`
- `step1` … `step10` (`.title` / `.description`) — one per Guest Onboarding Tour step
- `step1Member`, `step10Member` (`.title` / `.description`) — member-variant copy for the Welcome and CTA steps, used when `isGuestMode === false`
- `chatPin`, `chatToggle` (`.title` / `.description`) — the `feature-chat-2026-07` spotlight tour's copy

See `frontend/lib/providers/locales/en.json` / `zh-TW.json` for current values.

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
        ├─ User reaches last (CTA) step as a guest, clicks "Sign In" / "Register"
        │       → isTutorialOpen=false, router.push('/login' | '/register')
        ├─ User reaches last (CTA) step as a guest, clicks "Stay in Guest Mode"
        │       → isTutorialOpen=false (same as Skip/X — no navigation)
        ├─ User reaches last step as an authenticated member (reopened via HelpCircle)
        │       → renders member-variant copy (titleKeyMember/descriptionKeyMember) and a
        │         single "Done" button instead of Sign In/Register/Stay in Guest Mode
        │       → clicking "Done" → isTutorialOpen=false
        └─ Guest mode exits (user logs in)
                → exitGuestMode() → isTutorialOpen=false (reset)
                → if a "spotlight" tour was active at that moment, tutorial_seen_tours += activeTourId
                  (onboarding tours still never write to this key)

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
| `frontend/components/features/navigation/nav-bar.tsx` | Add `id="tutorial-target-*"` attributes for all 10 onboarding steps (desktop nav); HelpCircle uses `useTutorial()`; mobile hamburger menu duplicates the same nav items/targets for `< 768px` (see Note below) |
| `frontend/components/features/navigation/release-notes-popover.tsx` | Hosts `id="tutorial-target-release-notes"` (step 9); accepts a `disableTutorialTargetId?: boolean` prop so the NavBar's mobile-menu instance can omit the `id`, avoiding a duplicate-DOM-id when both the desktop and mobile instances are mounted at once |
| `frontend/components/features/articles/article-card.tsx` | Accepts `isFirstTutorialTarget?: boolean` to conditionally render `id="tutorial-target-chat-pin"` for the `feature-chat-2026-07` spotlight tour |
| `frontend/app/layout-shell.tsx` | Mount `<TutorialOverlay />` instead of `<TutorialModal />` |
| `frontend/lib/providers/locales/en.json` / `zh-TW.json` | `tutorial.*` keys grew from 4 to 10 onboarding steps, plus `step1Member`/`step10Member`, `stayGuest`, `chatPin`, `chatToggle` |
| `frontend/vitest.setup.ts` | Add `ResizeObserver` polyfill |

**Note on NavBar's mobile menu**: `nav-bar.tsx` renders a `< 768px` hamburger menu that duplicates every desktop nav item (including `ReleaseNotesPopover`) so it's reachable on mobile. Because the desktop instance is only CSS-hidden (`hidden md:flex`) rather than unmounted, both instances exist in the DOM simultaneously once the mobile menu opens — hence the `disableTutorialTargetId` prop on `ReleaseNotesPopover` (only the desktop instance keeps the `id`).

### Test Files
| File | Purpose |
|------|---------|
| `frontend/tests/unit/tutorial-overlay.test.tsx` | Replaces `tutorial-modal.test.tsx` |
| `frontend/tests/unit/tutorial-provider.test.tsx` | Replaces tutorial assertions previously in `guest-mode-context.test.tsx` |
| `frontend/tests/unit/use-tutorial-target.test.ts` | New |
| `frontend/tests/integration/guest-tutorial.spec.ts` | Rewritten for spotlight/navigation/mobile assertions |
