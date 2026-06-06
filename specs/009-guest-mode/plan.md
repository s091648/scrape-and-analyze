# Implementation Plan: Guest Mode

**Branch**: `009-guest-mode` | **Date**: 2026-05-30 | **Spec**: [spec.md](spec.md)

## Summary

Add an opt-in Guest Mode that lets users browse real first-page article data without creating an account. Guest Mode is triggered from the login page ("Continue as Guest"), managed as a pure frontend `sessionStorage`-backed context, and enforces limits in three places: articles (page 1 only, no pagination), settings (blocked with login/register prompt), and the knowledge graph (filtered to first-page article nodes). The backend requires no changes — all affected APIs are already public.

## Technical Context

**Language/Version**: TypeScript + React 19 (strict mode)

**Primary Dependencies**: Next.js 16 (App Router), NextAuth v4 (status watch only), Shadcn/UI, Tailwind CSS v4

**Storage**: `sessionStorage` key `guest_mode` (browser session lifetime; cleared on tab close or on real login)

**Testing**: Vitest (unit — GuestModeContext logic), Playwright (E2E — guest flow end-to-end)

**Target Platform**: Web browser

**Project Type**: Web application (frontend change only)

**Performance Goals**: Guest mode activate in < 100ms; page-1 article load same as regular page-1 load

**Constraints**:
- Must NOT change existing paywall behavior for unauthenticated non-guest users (zero regression)
- Must NOT modify NextAuth configuration or backend APIs
- Guest state must survive page refresh within the same browser session

**Scale/Scope**: Adds 1 new provider file; modifies 5 existing frontend files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. DDD (src/) | Pass (N/A) | Frontend-only; no `src/` changes |
| II. Atomic Frontend Architecture | Pass | New `GuestModeProvider` in `lib/providers/` (not `components/features/`); no Storybook required for providers |
| II. Storybook | Check | If a new guest-restricted prompt component is created in `components/features/`, it MUST have a story |
| III. Test Discipline | Pass | `GuestModeContext` logic should have Vitest unit tests |
| IV. Docker-First | Pass | No infra changes |
| V. CI/CD | Pass | No backend or migration changes |
| VI. Observability | Pass (N/A) | No new backend endpoints |
| VII. i18n | Required | 4 new i18n keys needed (see research.md) |

**Complexity Tracking**: No violations.

## Project Structure

### Documentation (this feature)

```text
specs/009-guest-mode/
├── plan.md              <- this file
├── research.md          complete
└── tasks.md             (next: /speckit-tasks)
```

### Source Code Changes

```text
frontend/
├── lib/providers/
│   ├── guest-mode-provider.tsx             ADD    -- GuestModeContext + useGuestMode hook
│   └── index.tsx                           MODIFY -- add GuestModeProvider to AppProviders
├── app/
│   ├── login/
│   │   └── login-page-content.tsx          MODIFY -- add "Continue as Guest" button
│   ├── home-page-content.tsx               MODIFY -- split isGuest logic (paywall vs guest mode)
│   ├── graph/
│   │   └── page.tsx                        MODIFY -- guest: limited graph; paywall: existing overlay
│   └── settings/
│       └── settings-page-content.tsx       MODIFY -- add guest-restricted guard at top
└── i18n/
    ├── en.json                             MODIFY -- 4 new keys
    └── zh-TW.json                          MODIFY -- 4 new keys
```

**No backend changes required.**

## Phase 0: Research

Complete — see [research.md](research.md).

Key decisions:
- `sessionStorage`-backed React Context (no NextAuth changes)
- `GuestModeProvider` auto-clears on `status === 'authenticated'`
- NavBar settings icon already hidden for guests (no NavBar change needed)
- Graph: client-side filtering to first-page article IDs (no backend change)
- Settings: guest guard in `settings-page-content.tsx`

## Phase 1: Design

### GuestModeProvider Design

```tsx
// lib/providers/guest-mode-provider.tsx
'use client'

const STORAGE_KEY = 'guest_mode'

interface GuestModeContextType {
  isGuestMode: boolean
  enterGuestMode: () => void
  exitGuestMode: () => void
}

export function GuestModeProvider({ children }: { children: React.ReactNode }) {
  const { status } = useSession()
  const [isGuestMode, setIsGuestMode] = useState(() => {
    if (typeof window === 'undefined') return false
    return sessionStorage.getItem(STORAGE_KEY) === 'true'
  })

  // Auto-exit on real login
  useEffect(() => {
    if (status === 'authenticated') exitGuestMode()
  }, [status])

  function enterGuestMode() {
    sessionStorage.setItem(STORAGE_KEY, 'true')
    setIsGuestMode(true)
  }
  function exitGuestMode() {
    sessionStorage.removeItem(STORAGE_KEY)
    setIsGuestMode(false)
  }

  return (
    <GuestModeContext.Provider value={{ isGuestMode, enterGuestMode, exitGuestMode }}>
      {children}
    </GuestModeContext.Provider>
  )
}
```

### AppProviders Update

```tsx
// lib/providers/index.tsx — GuestModeProvider inside SessionProviderWrapper (needs useSession)
<SessionProviderWrapper>
  <I18nProvider>
    <GuestModeProvider>
      <TopicProvider>{children}</TopicProvider>
    </GuestModeProvider>
  </I18nProvider>
</SessionProviderWrapper>
```

### home-page-content.tsx Logic Refactor

Replace single `isGuest` with two derived states:

```tsx
const { status } = useSession()
const { isGuestMode } = useGuestMode()

const isPaywall = status === 'unauthenticated' && !isGuestMode

// In useEffect: skip API call only for paywall, not for guest mode
useEffect(() => {
  if (isPaywall) { setIsLoading(false); return }
  fetchArticles({ page: isGuestMode ? 1 : page, ... })
}, [..., isPaywall, isGuestMode])

// In JSX:
// isPaywall     -> existing GUEST_PLACEHOLDER_ARTICLES + blur overlay (unchanged code path)
// isGuestMode   -> real articles, no pagination controls
// authenticated -> existing full experience
```

### Graph Page: Guest Filtering

When in guest mode, fetch first-page article IDs and pass to `KnowledgeGraph` as filter:

```tsx
useEffect(() => {
  if (!isGuestMode || !selectedTopicId) return
  fetchArticles({ page: 1, topic_id: selectedTopicId }).then(data => {
    setFirstPageArticleIds(new Set(data.items.map(a => a.id)))
  })
}, [isGuestMode, selectedTopicId])
```

`KnowledgeGraph` accepts optional `articleIdFilter?: Set<string>` prop. When provided:
1. Keep article nodes where `node.articleId` is in the filter set
2. Keep edges between kept nodes
3. Keep tag/group nodes with at least one remaining edge

### Settings Guest Guard

```tsx
// settings-page-content.tsx — add at top before existing auth check
const { isGuestMode } = useGuestMode()

if (isGuestMode) {
  return (
    <div className="...">  {/* simple inline prompt, no extracted component */}
      <h2>{t('guest.restrictedTitle')}</h2>
      <p>{t('guest.restrictedMessage')}</p>
      <Link href="/login">...</Link>
      <Link href="/register">...</Link>
    </div>
  )
}
```

### Login Page: "Continue as Guest" Button

Add below the Google sign-in button with ghost/text variant (lower emphasis):

```tsx
<Button
  variant="ghost"
  className="w-full text-sm text-muted-foreground"
  onClick={() => { enterGuestMode(); router.push('/') }}
>
  {t('guest.continueAsGuest')}
</Button>
```

## i18n Keys Required

| Key | English | zh-TW |
|-----|---------|-------|
| `guest.continueAsGuest` | "Continue as Guest" | "以訪客身份繼續" |
| `guest.restrictedTitle` | "Account required" | "需要帳號" |
| `guest.restrictedMessage` | "Sign in or create an account to access settings." | "請登入或建立帳號以使用設定功能。" |
| `guest.graphLimitedPreview` | "Viewing a limited preview — sign in for the full graph." | "目前顯示有限預覽，登入後可查看完整圖譜。" |

## Implementation Sequence

1. **i18n keys** — add 4 keys to `en.json` and `zh-TW.json`
2. **GuestModeProvider** — create `lib/providers/guest-mode-provider.tsx`; update `lib/providers/index.tsx`
3. **Login page** — add "Continue as Guest" button to `login-page-content.tsx`
4. **Home page** — refactor `isGuest` to `isPaywall + isGuestMode` in `home-page-content.tsx`
5. **Settings guard** — add guest check to `settings-page-content.tsx`
6. **Graph page** — add guest filter mode to `graph/page.tsx`; update `KnowledgeGraph` to accept `articleIdFilter` prop
7. **Tests** — Vitest unit tests for `GuestModeContext`; Playwright E2E for guest flow

## Quickstart: Development

```bash
# Start frontend dev server
cd frontend && npm run dev

# Test guest mode flow:
# 1. Open http://localhost:3000/login -> see "Continue as Guest" button
# 2. Click -> redirected to / with real page-1 articles (no blur)
# 3. Verify: no pagination controls; no Settings icon in NavBar
# 4. Navigate to /settings directly -> see "Account required" prompt
# 5. Navigate to /graph -> see limited graph (<=20 article nodes)
# 6. Refresh page -> still in guest mode
# 7. Click Login, log in -> guest mode clears, full access restored

# Test paywall regression:
# 1. Open incognito, navigate to / WITHOUT clicking "Continue as Guest"
# 2. Must still see blurred placeholder articles + lock overlay (existing behavior)

# Run unit tests
cd frontend && npm run test

# Run E2E
cd frontend && npm run test:e2e
```
