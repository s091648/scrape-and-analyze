# UI Contract: Guest Tutorial Mode

**Feature**: 015-guest-tutorial-mode  
**Date**: 2026-06-29

---

## TutorialModal Component

**File**: `frontend/components/features/tutorial/tutorial-modal.tsx`

### Props

```typescript
// No external props — reads all state from useGuestMode() context
// Component is self-contained; mount it once at layout level (or in providers)
```

### Consumed Context (from `useGuestMode()`)

| Field | Type | Description |
|-------|------|-------------|
| `isTutorialOpen` | `boolean` | Whether the modal is visible |
| `tutorialStep` | `number` | Current step index (0-based) |
| `closeTutorial` | `() => void` | Close and mark as seen |
| `nextTutorialStep` | `() => void` | Advance to next step |
| `prevTutorialStep` | `() => void` | Go back one step |

### Rendering Contract

- **Hidden state**: When `isTutorialOpen === false`, component renders nothing (`null`)
- **Overlay**: Renders a `Dialog` with backdrop blur; clicking backdrop closes the tutorial
- **Step indicator**: Row of `N` dots (N = `TUTORIAL_STEPS.length`); active dot is filled/highlighted
- **Icon area**: Displays `TutorialStep.icon` if defined; 48×48px; centered
- **Title**: `t(TUTORIAL_STEPS[tutorialStep].titleKey)` — heading-level text
- **Description**: `t(TUTORIAL_STEPS[tutorialStep].descriptionKey)` — body text, max 2-3 lines
- **Navigation row**:
  - Left: "Back" button (`variant="ghost"`) — hidden on step 0, visible on steps 1+
  - Right: "Next" button (`variant="default"`) — visible on steps 0 to N-2
  - Right (last step only): "Sign In" button (`variant="default"`) + "Register" button (`variant="outline"`)
  - Top-right: "X" close button (always visible)
  - Bottom-left: "Skip" text button (`variant="link"`) — visible on all steps except last

### Accessibility

- `Dialog` ARIA pattern: `role="dialog"`, `aria-modal="true"`, `aria-labelledby` pointing to title
- Focus trap: Radix UI `Dialog` handles this automatically
- `Escape` key: Closes modal (calls `closeTutorial()`)
- Tab order: Step indicator (non-interactive) → Content → Navigation buttons

---

## GuestModeContext Additions

**File**: `frontend/lib/providers/guest-mode-provider.tsx`

### Extended Interface

```typescript
interface GuestModeContextType {
  // Existing (unchanged)
  isGuestMode: boolean
  enterGuestMode: () => void
  exitGuestMode: () => void

  // New: Tutorial
  isTutorialOpen: boolean
  tutorialStep: number
  openTutorial: () => void
  closeTutorial: () => void
  nextTutorialStep: () => void
  prevTutorialStep: () => void
}
```

### Behavioral Contract

| Action | Pre-condition | State change | Side effect |
|--------|--------------|--------------|-------------|
| `enterGuestMode()` | — | `isGuestMode=true`; if `!sessionStorage.get('guest_tutorial_seen')` → `isTutorialOpen=true, tutorialStep=0` | Sets `sessionStorage 'guest_mode'='true'` |
| `exitGuestMode()` | — | `isGuestMode=false`, `isTutorialOpen=false`, `tutorialStep=0` | Removes `sessionStorage 'guest_mode'` |
| `openTutorial()` | `isGuestMode=true` | `isTutorialOpen=true`, `tutorialStep=0` | — |
| `closeTutorial()` | `isTutorialOpen=true` | `isTutorialOpen=false` | Sets `sessionStorage 'guest_tutorial_seen'='true'` |
| `nextTutorialStep()` | `tutorialStep < TUTORIAL_STEPS.length - 1` | `tutorialStep++` | — |
| `prevTutorialStep()` | `tutorialStep > 0` | `tutorialStep--` | — |

**Guard**: `openTutorial()` is a no-op if `!isGuestMode`.

---

## NavBar HelpCircle Icon

**File**: `frontend/components/features/navigation/nav-bar.tsx`

### Rendering Contract

```typescript
// Conditionally render in NavBar right-side icon group:
{isGuestMode && (
  <button
    onClick={openTutorial}
    aria-label={t('tutorial.reopenLabel')}  // i18n key: "Reopen tutorial"
    className="..."
  >
    <HelpCircle className="h-5 w-5" />
  </button>
)}
```

- Position: In the right-side icon group, before the language/theme toggles (or after settings icon slot)
- Size: `h-5 w-5` (matching existing NavBar icons)
- Tooltip: Uses existing `Tooltip` primitive with `t('tutorial.reopenLabel')` text

---

## TUTORIAL_STEPS Config

**File**: `frontend/components/features/tutorial/tutorial-steps.ts`

```typescript
export const TUTORIAL_STEPS: TutorialStep[] = [
  { id: 'welcome',  titleKey: 'tutorial.step1.title', descriptionKey: 'tutorial.step1.description', icon: Sparkles  },
  { id: 'articles', titleKey: 'tutorial.step2.title', descriptionKey: 'tutorial.step2.description', icon: Newspaper },
  { id: 'graph',    titleKey: 'tutorial.step3.title', descriptionKey: 'tutorial.step3.description', icon: GitBranch },
  { id: 'cta',      titleKey: 'tutorial.step4.title', descriptionKey: 'tutorial.step4.description', icon: LogIn     },
]

export type TutorialStepId = typeof TUTORIAL_STEPS[number]['id']
```

- Adding or removing a step requires only editing this array — all consuming components derive step count from `TUTORIAL_STEPS.length`

---

## i18n Contract

All keys must exist in both `en.json` and `zh-TW.json`. Missing keys fall back to English (existing I18nProvider behavior).

**Required new keys** (see `data-model.md` for full values):
```
tutorial.stepOf
tutorial.skip
tutorial.back
tutorial.next
tutorial.getStarted
tutorial.signIn
tutorial.register
tutorial.reopenLabel
tutorial.step1.title
tutorial.step1.description
tutorial.step2.title
tutorial.step2.description
tutorial.step3.title
tutorial.step3.description
tutorial.step4.title
tutorial.step4.description
```
