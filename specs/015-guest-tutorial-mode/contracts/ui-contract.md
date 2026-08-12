# UI Contract: Guest Tutorial Mode & Feature Spotlight

**Feature**: 015-guest-tutorial-mode
**Date**: 2026-06-29
**Updated**: 2026-07-05 (synced nav-row CTA behavior, TUTORIAL_TOURS config, i18n key list, and NavBar mobile-menu note with the shipped implementation)

---

## TutorialOverlay Component

**File**: `frontend/components/features/tutorial/tutorial-overlay.tsx`

### Props

```typescript
// No external props — reads all state from useTutorial() context.
// Component is self-contained; mount it once at layout level.
```

### Consumed Context (from `useTutorial()`)

| Field | Type | Description |
|-------|------|-------------|
| `isTutorialOpen` | `boolean` | Whether the overlay/card is visible |
| `activeTourId` | `string \| null` | Which `TutorialTour` (from the registry) is active |
| `tutorialStep` | `number` | Current step index within the active tour (0-based) |
| `closeTutorial` | `() => void` | Close; marks spotlight tours as seen |
| `nextTutorialStep` | `() => void` | Advance to next step |
| `prevTutorialStep` | `() => void` | Go back one step |

### Rendering Contract

- **Hidden state**: When `isTutorialOpen === false`, component renders nothing (`null`)
- **Route sync**: On `[tutorialStep, activeTourId]` change, if the resolved step's `route` differs from the current pathname, `router.push(route)`
- **Target resolution**: `rect = useTutorialTarget(isMobile ? undefined : step.targetId)`
- **Spotlight mode** (`rect !== null`, desktop only):
  - Full-screen `fixed inset-0` transparent div, `pointer-events: auto` — blocks all clicks across the viewport, including over the highlighted target (highlight is visual-only, not interactive; FR-013)
  - A div positioned to match `rect` (`top/left/width/height` from `getBoundingClientRect()`), `box-shadow: 0 0 0 9999px rgba(0,0,0,0.6)`, rounded corners — creates the dimmed backdrop with a transparent cutout over the target
  - Description card anchored via `PopoverAnchor` with `virtualRef` pointing at `rect`, rendered through `PopoverContent` (title/description/icon/step dots/nav buttons) — Radix Popper handles collision/flip so the card stays on-screen
  - No `Dialog` wrapper; Escape-to-close implemented via a manual `keydown` listener while `isTutorialOpen`
- **Centered-card mode** (`rect === null` — no `targetId` (Welcome/CTA-without-target), mobile viewport, or 3s target-not-found timeout):
  - Renders the existing `Dialog`/`DialogContent` centered layout (same visual content as the pre-redesign `TutorialModal`)
  - Backdrop click, Escape, and focus trap come for free from Radix `Dialog`
- **Step indicator**: Row of `N` dots (N = active tour's `steps.length`); active dot is filled/highlighted — present in both modes
- **Icon area**: Displays `TutorialStep.icon` if defined; 48×48px — centered-card mode only (omitted in spotlight mode, where the highlight itself is the visual anchor)
- **Title / Description**: `t(step.titleKey)` / `t(step.descriptionKey)`
- **Navigation row** (both modes):
  - Left: "Back" button (`variant="ghost"`) — hidden on step 0
  - Right: "Next" button (`variant="default"`) — visible on steps 0 to N-2
  - Right (last step only, `step.isCta === true`), branches on `isGuestMode`:
    - **Guest** (`isGuestMode === true`): "Stay in Guest Mode" (`variant="ghost"`, closes without navigating) + "Register" (`variant="outline"`) + "Sign In" (`variant="default"`)
    - **Member** (`isGuestMode === false`, e.g. reopened via HelpCircle): none of the above render — falls through to the plain "Done" button below instead, and `titleKey`/`descriptionKey` are swapped for `titleKeyMember`/`descriptionKeyMember` when present
  - Right (last step, non-CTA tours, or CTA step viewed by a member): "Done" button (`variant="default"`), closes the tour
  - Top-right: "X" close button (always visible)
  - Bottom-left: "Skip" text button (`variant="link"`) — visible on all steps except last

### Accessibility

- Centered-card mode: Radix `Dialog` ARIA pattern (`role="dialog"`, `aria-modal="true"`, `aria-labelledby`), focus trap automatic
- Spotlight mode: description card gets `role="dialog"` + `aria-labelledby`/`aria-describedby` manually; initial focus moves to the card on open; `Escape` closes via manual listener
- Tab order: description card content → navigation buttons (highlighted target itself is not part of the tab order while a tour is open, since it's non-interactive)

---

## `useTutorialTarget` Hook

**File**: `frontend/components/features/tutorial/use-tutorial-target.ts`

```typescript
function useTutorialTarget(targetId: string | undefined): DOMRect | null
```

| Input | Output | Behavior |
|-------|--------|----------|
| `undefined` | `null` | No-op — caller renders centered-card mode |
| `string`, element exists immediately | `DOMRect` | Returned on first effect run |
| `string`, element mounts async (e.g. post-navigation) | `DOMRect` (once found) | Polls via `requestAnimationFrame` up to 3s |
| `string`, element never found within 3s | `null` | Caller falls back to centered-card mode |

Once a rect is found, it is recalculated on:
- `window resize`
- `scroll` (capture phase, so non-window scroll containers are also caught)
- `ResizeObserver` on the target element itself (covers content-driven size changes, e.g. a skeleton resolving to real content)

---

## `useIsMobile` Hook

**File**: `frontend/components/features/tutorial/use-is-mobile.ts`

```typescript
function useIsMobile(): boolean // true when window.innerWidth < 768, updates on resize
```

---

## TutorialProvider

**File**: `frontend/lib/providers/tutorial-provider.tsx`

### Interface

```typescript
interface TutorialContextType {
  isTutorialOpen: boolean
  activeTourId: string | null
  tutorialStep: number
  openTutorial: (tourId?: string) => void  // default: "guest-onboarding"
  closeTutorial: () => void
  nextTutorialStep: () => void
  prevTutorialStep: () => void
}
```

### Behavioral Contract

| Action | Pre-condition | State change | Side effect |
|--------|--------------|--------------|-------------|
| (internal) `isGuestMode` becomes `true` | `sessionStorage['tutorial_onboarding_dismissed']` not set | `openTutorial("guest-onboarding")` | — |
| (internal) `isGuestMode` becomes `false` | — | — | Clears `sessionStorage['tutorial_onboarding_dismissed']` |
| (internal) pathname changes | some `kind:"spotlight"` tour matches route + unseen + role + `!isTutorialOpen` | `openTutorial(tour.id)` | — |
| `openTutorial(tourId?)` | `isGuestMode=true` OR `status==='authenticated'` | `isTutorialOpen=true`, `activeTourId=tourId ?? "guest-onboarding"`, `tutorialStep=0` | — (bypasses the `tutorial_onboarding_dismissed` check — manual reopen always works) |
| `closeTutorial()` | `isTutorialOpen=true` | `isTutorialOpen=false` | If active tour `kind==="spotlight"`, append its id to `localStorage['tutorial_seen_tours']`; if `kind==="onboarding"`, set `sessionStorage['tutorial_onboarding_dismissed']='true'` |
| `nextTutorialStep()` | `tutorialStep < activeTour.steps.length - 1` | `tutorialStep++` | — (route sync happens in `TutorialOverlay`, not here) |
| `prevTutorialStep()` | `tutorialStep > 0` | `tutorialStep--` | — |

**Guard**: `openTutorial()` is a no-op if `status === 'unauthenticated' && !isGuestMode` (paywall state) — applies to both tour kinds.

**Mutual exclusion**: the spotlight auto-trigger effect checks `!isTutorialOpen` before firing, so a Guest Onboarding Tour in progress is never interrupted by a Feature Spotlight tour, and vice versa (FR-019).

**Decoupled from `next/navigation`**: `TutorialProvider` reads `usePathname()` (to decide *whether* to trigger) but never calls `router.push` itself — imperative navigation lives entirely in `TutorialOverlay`, keeping the provider trivially testable without mocking `next/navigation`'s router.

---

## NavBar Changes

**File**: `frontend/components/features/navigation/nav-bar.tsx`

```typescript
<Link href={`/articles${topicParam}`} id="tutorial-target-articles" ...>{t("nav.articles")}</Link>
<Link href={`/graph${topicParam}`} id="tutorial-target-graph" ...>{t("nav.knowledgeGraph")}</Link>
// ... in the unauthenticated branch:
<Button asChild id="tutorial-target-login" ...><Link href="/login">{t("nav.login")}</Link></Button>

// HelpCircle, unchanged visibility rule, now sourced from useTutorial():
{(isGuestMode || !!session) && (
  <button onClick={() => openTutorial()} aria-label={t('tutorial.reopenLabel')}>
    <HelpCircle className="h-5 w-5" />
  </button>
)}
```

- **Visible to**: guest mode users AND authenticated members
- **Hidden from**: pure unauthenticated users (paywall state)

**Mobile menu note**: below `768px`, NavBar renders a hamburger-triggered mobile panel that duplicates every desktop nav item (Articles/Graph/Tags links, language, theme, GitHub, docs, release notes, HelpCircle, login/logout) so they're reachable on small screens. The desktop versions are only CSS-hidden (`hidden md:flex`), not unmounted, so when the mobile menu is open both instances exist in the DOM at once. `ReleaseNotesPopover`'s mobile instance is rendered with `disableTutorialTargetId` to avoid a duplicate `id="tutorial-target-release-notes"`.

---

## TUTORIAL_TOURS Config

**File**: `frontend/components/features/tutorial/tutorial-registry.ts`

```typescript
export const TUTORIAL_TOURS: TutorialTour[] = [
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
  {
    id: "feature-chat-2026-07",
    kind: "spotlight",
    steps: [
      { id: "chat-pin",    route: "/articles", titleKey: "tutorial.chatPin.title",    descriptionKey: "tutorial.chatPin.description",    icon: Sparkles,      targetId: "tutorial-target-chat-pin" },
      { id: "chat-toggle", route: "/articles", titleKey: "tutorial.chatToggle.title", descriptionKey: "tutorial.chatToggle.description", icon: MessageSquare, targetId: "tutorial-target-chat-toggle" },
    ],
  },
]
```

- Adding a step to an existing tour, or adding a new `kind: "spotlight"` tour, only requires editing this array — all consuming components derive step count / target / route from it
- Invariant enforced by convention (not type-checked): every step in a `kind: "spotlight"` tour must share the same `route`
- `titleKeyMember`/`descriptionKeyMember` and `isCta` are optional per-step overrides — only the onboarding tour's `welcome` and `cta` steps currently set them

---

## i18n Contract

All keys must exist in both `en.json` and `zh-TW.json`. Missing keys fall back to English (existing I18nProvider behavior).

```
tutorial.stepOf
tutorial.skip
tutorial.back
tutorial.next
tutorial.getStarted
tutorial.signIn
tutorial.register
tutorial.stayGuest
tutorial.done
tutorial.reopenLabel
tutorial.step1.title / .description         (welcome)
tutorial.step1Member.title / .description   (welcome, member-variant)
tutorial.step2.title / .description         (articles)
tutorial.step3.title / .description         (graph)
tutorial.step4.title / .description         (tags)
tutorial.step5.title / .description         (language)
tutorial.step6.title / .description         (theme)
tutorial.step7.title / .description         (github)
tutorial.step8.title / .description         (docs)
tutorial.step9.title / .description         (release notes)
tutorial.step10.title / .description        (cta)
tutorial.step10Member.title / .description  (cta, member-variant)
tutorial.chatPin.title / .description       (feature-chat-2026-07)
tutorial.chatToggle.title / .description    (feature-chat-2026-07)
```
