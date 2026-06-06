# Implementation Plan: Article Sharing via URL

**Branch**: `008-article-sharing` | **Date**: 2026-05-30 | **Spec**: [spec.md](spec.md)

## Summary

Enable users to share specific articles via URL by: (1) syncing the open article's ID into the URL query params on the main page, (2) adding a share/copy icon to `ArticleCard`, and (3) creating a standalone `/articles/[articleId]` route with a NavBar-free layout. The backend already exposes a public `GET /articles/{article_id}` endpoint — no backend changes are needed.

## Technical Context

**Language/Version**: TypeScript + React 19 (strict mode)

**Primary Dependencies**: Next.js 16 (App Router), NextAuth v4, Shadcn/UI, lucide-react, Tailwind CSS v4

**Storage**: N/A (read-only frontend feature, backend already provides data)

**Testing**: Vitest (unit), Playwright (E2E)

**Target Platform**: Web browser (desktop + mobile)

**Project Type**: Web application (frontend change only)

**Performance Goals**: URL sync within 200ms of dialog open/close; share copy within 500ms

**Constraints**: Must not break existing `useSearchParams` / pagination URL state; must not add NavBar to standalone article page

**Scale/Scope**: Touches 3 existing files + adds 2 new route files + 1 new layout utility component

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. DDD (src/) | ✅ N/A | Frontend-only change; no `src/` code touched |
| II. Atomic Frontend Architecture | ✅ Pass | `ArticleCard` modified (existing feature component); `LayoutShell` utility in `app/` (not `components/features/`); new page files are Next.js routes, not shared components — Storybook not required |
| II. Storybook | ✅ Pass | No new `components/features/` components introduced |
| III. Test Discipline | ✅ Pass | New i18n keys and share behavior should have Vitest unit tests |
| IV. Docker-First | ✅ Pass | Dev: `cd frontend && npm run dev`; no infra changes |
| V. CI/CD | ✅ Pass | No backend or migration changes |
| VI. Observability | ✅ N/A | No new backend endpoints |
| VII. i18n | ⚠️ Required | `copy.success` and `copy.failed` strings need locale file entries |

**Complexity Tracking**: No violations.

## Project Structure

### Documentation (this feature)

```text
specs/008-article-sharing/
├── plan.md              ← this file
├── research.md          ✅ complete
├── contracts/
│   └── url-schema.md    ← URL param conventions
└── tasks.md             (next: /speckit-tasks)
```

### Source Code Changes

```text
frontend/
├── app/
│   ├── layout.tsx                          MODIFY — extract LayoutShell, conditional NavBar
│   ├── layout-shell.tsx                    ADD    — client component, pathname-based NavBar toggle
│   ├── articles/
│   │   └── [articleId]/
│   │       └── page.tsx                   ADD    — standalone article share page
│   └── home-page-content.tsx              MODIFY — read article param, sync URL on open/close
├── components/features/articles/
│   └── article-card.tsx                   MODIFY — add share icon + clipboard logic
└── i18n/
    ├── en.json                             MODIFY — add copy.success, copy.failed keys
    └── zh-TW.json                          MODIFY — add copy.success, copy.failed keys
```

**No backend changes required.**

## Phase 0: Research

Complete — see [research.md](research.md).

Key decisions:
- No backend changes
- `LayoutShell` client component for conditional NavBar (not route group restructure)
- Share URL built using `useTopic()` context (no new prop drilling)
- `router.replace()` for URL sync (no history stack buildup)

## Phase 1: Design

### LayoutShell Architecture

The root `app/layout.tsx` becomes a thin wrapper. A new `app/layout-shell.tsx` client component handles conditional NavBar rendering:

```tsx
// app/layout-shell.tsx
'use client'
import { usePathname } from 'next/navigation'
import { NavBar } from '@/components/features/navigation/nav-bar'

export function LayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isStandalone = pathname.startsWith('/articles/')

  return (
    <>
      {!isStandalone && <NavBar />}
      <main className={isStandalone
        ? 'min-h-screen flex items-center justify-center p-6'
        : 'container mx-auto px-6 py-8 pt-24'
      }>
        {children}
      </main>
    </>
  )
}
```

### URL Sync in home-page-content.tsx

```
On article open:
  router.replace(`/?${params}` where params includes article=<id> and preserves topic/filters)

On article close:
  router.replace(`/?${params}` where params removes article key)

On mount with article param present:
  → setOpen(true) for that article ID (triggers existing fetchArticleById effect)
```

The `ArticleCard` already manages its own `open` state. URL sync moves up to `home-page-content.tsx` where it can use `router` + `searchParams`:

- Option A: Pass `onOpen`/`onClose` callbacks down to `ArticleCard` (breaks encapsulation slightly)
- Option B: Move `open` state management to `home-page-content.tsx` and pass as prop
- **Chosen Option B**: `home-page-content.tsx` owns `openArticleId` state, passes `open` and `onOpenChange` to `ArticleCard` as controlled props. This is cleaner for URL sync coordination.

### ArticleCard Share Button

Add a `Share2` icon from lucide-react (or `Link` icon) next to the existing `ExternalLink`. Both are `opacity-0 group-hover:opacity-100`.

```tsx
const [copied, setCopied] = useState(false)

async function handleShare(e: React.MouseEvent) {
  e.stopPropagation()
  const url = `${window.location.origin}/?topic=${topicId}&article=${id}`
  try {
    await navigator.clipboard.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  } catch {
    // fallback: show error state
  }
}
```

### Standalone Article Page

`app/articles/[articleId]/page.tsx` is a client component that:
1. Reads `articleId` from params
2. Calls `fetchArticleById(articleId, locale)` on mount
3. Renders a single `ArticleCard` (or the full `ArticleDetailDialog` content inline)
4. Shows loading skeleton and 404 state

Since the root layout's `LayoutShell` detects `/articles/` and hides NavBar + adjusts padding, this page only needs to render the card.

## Implementation Sequence

1. **i18n keys** — add `copy.success`, `copy.failed` to both locale files
2. **LayoutShell** — create `app/layout-shell.tsx`, update `app/layout.tsx` to use it
3. **URL sync in home-page-content** — lift `openArticleId` state, implement `router.replace` on open/close, auto-open from URL param on mount
4. **ArticleCard share button** — add share icon, clipboard logic, copied feedback
5. **Standalone page** — create `app/articles/[articleId]/page.tsx`
6. **Tests** — Vitest unit tests for share URL generation; Playwright E2E for share flow

## Quickstart: Development

```bash
# Start frontend dev server
cd frontend && npm run dev

# Test share flow:
# 1. Open http://localhost:3000, select a topic
# 2. Click any article card → verify URL updates to /?topic=...&article=...
# 3. Click share icon → verify URL copied to clipboard
# 4. Paste URL in new tab → verify article dialog auto-opens
# 5. Navigate to /articles/<uuid> → verify standalone page with no NavBar
# 6. Close dialog on main page → verify article param removed from URL

# Run unit tests
cd frontend && npm run test

# Run E2E
cd frontend && npm run test:e2e
```
