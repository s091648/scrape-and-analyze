# Tasks: Article Sharing via URL

**Branch**: `008-article-sharing` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Prerequisites**: plan.md, spec.md, research.md, contracts/url-schema.md

**User Stories** (from spec.md):
- US1 (P1): URL 同步 — 開啟文章時更新 URL；從 URL 自動開啟對應文章
- US2 (P2): 複製分享連結 — share icon + clipboard copy + 視覺回饋
- US3 (P3): 獨立文章分享頁 — /articles/[articleId] 無 NavBar 的獨立頁面

---

## Phase 1: Setup (i18n)

**Purpose**: 新增所有功能所需的 i18n key，確保後續實作可直接使用 `t()` 而不留 hardcoded 字串。

- [x] T001 [P] Add `copy.success` and `copy.failed` keys to `frontend/i18n/en.json`
- [x] T002 [P] Add `copy.success` and `copy.failed` keys to `frontend/i18n/zh-TW.json`

**Checkpoint**: 兩個 locale 檔案都有新 key → Phase 2 可開始

---

## Phase 2: Foundational (LayoutShell)

**Purpose**: 建立讓 `/articles/*` 路由隱藏 NavBar 的條件式 layout 架構。US3 依賴此 phase。

**⚠️ CRITICAL**: Phase 2 必須在 US3 開始前完成

- [x] T003 Create `frontend/app/layout-shell.tsx` — 'use client' component that uses `usePathname()` to conditionally render `<NavBar />` and adjust `<main>` className: hide NavBar and remove `pt-24` for paths starting with `/articles/`
- [x] T004 Update `frontend/app/layout.tsx` to replace inline `<NavBar />` + `<main>` with `<LayoutShell>{children}</LayoutShell>` (depends on T003)

**Checkpoint**: 造訪任何 `/articles/*` URL → 頁面無 NavBar，padding 正常

---

## Phase 3: User Story 1 — URL Sync (Priority: P1) MVP

**Goal**: 使用者點開文章對話框時，`?article=<id>` 被加入 URL；關閉後移除；直接開啟含 `article` param 的 URL 會自動展開對應對話框。

**Independent Test**: 手動開啟/關閉文章 dialog → URL 即時更新；複製帶 `article` param 的 URL 貼到新分頁 → 對話框自動展開。

### Implementation for User Story 1

- [x] T005 [US1] Refactor `frontend/components/features/articles/article-card.tsx` to support optional controlled props: add `open?: boolean` and `onOpenChange?: (open: boolean) => void` to component signature; when these props are provided the component uses them instead of internal `useState`; when absent, fall back to existing internal state behavior (backward compatible)
- [x] T006 [US1] Update `frontend/app/home-page-content.tsx` to:
  1. Add `openArticleId` state (`string | null`)
  2. Read `article` search param on mount — if present, set `openArticleId` to that value
  3. Pass `open={openArticleId === a.id}` and `onOpenChange={(v) => { setOpenArticleId(v ? a.id : null) }}` to each `<ArticleCard>`
  4. Add `useEffect` watching `openArticleId` — call `router.replace()` to add or remove `article` query param while preserving `topic` and other existing params

**Checkpoint**: US1 is independently testable — open article → URL updates; close → URL reverts; paste URL → auto-opens

---

## Phase 4: User Story 2 — Share Icon & Clipboard (Priority: P2)

**Goal**: ArticleCard hover 顯示 share icon；點擊後複製含 `?topic=<id>&article=<id>` 的完整 URL 到剪貼簿並顯示 2 秒成功回饋；Clipboard API 不可用時顯示錯誤。

**Independent Test**: hover card → share icon 出現；click share → URL 被複製到剪貼簿；icon 切換到 check 狀態 2 秒後恢復。

### Implementation for User Story 2

- [x] T007 [US2] Update `frontend/components/features/articles/article-card.tsx` to add share functionality:
  1. Import `useTopic` from `@/lib/providers` and `useI18n` (for `t('copy.success')` / `t('copy.failed')`)
  2. Add `copied` state (`boolean`)
  3. Add `handleShare` async function: build URL as `${window.location.origin}/?topic=${selectedTopicId}&article=${id}`, call `navigator.clipboard.writeText(url)`, on success set `copied = true` and reset after 2000ms, on failure show error feedback
  4. Add share icon button (use `Share2` or `Link` icon from lucide-react) next to existing `ExternalLink` icon with same `opacity-0 group-hover:opacity-100 transition-opacity` pattern; when `copied === true` swap to `Check` icon; add `onClick={handleShare}` with `e.stopPropagation()`

**Checkpoint**: US2 is independently testable — share icon appears on hover, clipboard receives correct URL, icon shows feedback

---

## Phase 5: User Story 3 — Standalone Article Page (Priority: P3)

**Goal**: `/articles/<articleId>` 顯示一個無 NavBar、無 FilterBar、無分頁的獨立頁面，只展示對應文章的 ArticleCard；文章不存在時顯示 404 訊息。

**Independent Test**: 造訪 `/articles/<valid-uuid>` → 頁面無 NavBar、只有文章卡片；造訪 `/articles/<invalid-uuid>` → 404 訊息。

**Prerequisite**: T003, T004 (LayoutShell) must be complete

### Implementation for User Story 3

- [x] T008 [US3] Create `frontend/app/articles/[articleId]/page.tsx` as a 'use client' component:
  1. Read `articleId` from `useParams()`
  2. On mount, call `fetchArticleById(articleId, locale)` from `@/lib/api/articles`
  3. While loading, show `<ArticleCardSkeleton />`
  4. On 404 / error, show a centered error card with message and link back to home
  5. On success, render a centered `<ArticleCard>` with `open={false}` and no `onOpenChange` prop (card-only display, no dialog auto-open on this page since the card IS the full page experience)

**Checkpoint**: US3 is independently testable — `/articles/<uuid>` renders article card with no NavBar; `/articles/invalid` shows 404

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 邊界情境處理與可及性補強

- [x] T009 [P] Add `aria-label` for the share icon button in `frontend/components/features/articles/article-card.tsx` (use `t('copy.shareArticle')` — add this key to both locale files)
- [x] T010 [P] Handle edge case in `frontend/app/home-page-content.tsx`: if `article` param is present in URL but the article is not found in the current page's article list, silently clear the param (the detail will still load via `fetchArticleById` inside ArticleCard)
- [ ] T011 Run the quickstart.md manual verification checklist: open article → URL sync; share icon → clipboard; paste URL → auto-open; `/articles/<uuid>` → standalone page; close dialog → URL cleared

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — run immediately in parallel
- **Phase 2 (Foundational)**: No dependencies — run in parallel with Phase 1
- **Phase 3 (US1)**: Depends on Phase 1 (i18n keys available); does NOT depend on Phase 2
- **Phase 4 (US2)**: Depends on Phase 3 (T005 — ArticleCard controlled props); also depends on Phase 1
- **Phase 5 (US3)**: Depends on Phase 2 (T003, T004 — LayoutShell must exist); independent of US1/US2
- **Phase 6 (Polish)**: Depends on Phases 3–5

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 1 setup — can start immediately
- **US2 (P2)**: Depends on T005 from US1 (controlled props added to ArticleCard)
- **US3 (P3)**: Depends on Phase 2 (LayoutShell) — independent of US1/US2

### Within Each User Story

- T005 (ArticleCard refactor) must complete before T006 (home-page-content changes)
- T003 must complete before T004 (layout.tsx depends on LayoutShell component)

### Parallel Opportunities

- T001 and T002 (i18n files) can run in parallel
- T003 (LayoutShell) can run in parallel with T001/T002
- T007 (US2 share icon) can run in parallel with T008 (US3 standalone page) after T005 completes

---

## Parallel Example: US1

```
After Phase 1 completes:
  Task T005: Refactor ArticleCard for controlled props (frontend/components/features/articles/article-card.tsx)

After T005 completes:
  Task T006: Update home-page-content for URL sync (frontend/app/home-page-content.tsx)
  Task T007: Add share icon to ArticleCard (frontend/components/features/articles/article-card.tsx) [WAIT — same file as T005, do after T005]

After Phase 2 completes:
  Task T008: Create standalone article page (frontend/app/articles/[articleId]/page.tsx) [can parallel with T006]
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1 (T001, T002) — i18n keys
2. Complete US1 (T005, T006) — URL sync
3. **STOP and VALIDATE**: Open article → URL updates; paste URL → auto-opens
4. Demo shareable URL to user

### Incremental Delivery

1. Phase 1 + US1 → URL sync working (shareable link via address bar)
2. Add US2 → share icon makes copying one-click
3. Add Phase 2 + US3 → standalone share page for clean previews
4. Add Polish → aria-labels, edge cases

---

## Notes

- [P] tasks = different files or no dependencies on incomplete sibling tasks
- T005 and T007 both modify `article-card.tsx` — do T005 first, T007 after
- The standalone page (US3) shows ArticleCard in display-only mode (no dialog trigger needed since the full card IS the page)
- Clipboard API requires `https://` or `localhost` — will fail in non-secure dev environments; test on localhost
- `router.replace()` is used throughout (not `push()`) to avoid browser history accumulation
