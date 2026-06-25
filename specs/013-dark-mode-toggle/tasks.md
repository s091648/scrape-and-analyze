# Tasks: Light / Dark / Auto Theme Toggle

**Input**: `specs/013-dark-mode-toggle/`

**Prerequisites**: plan.md ✅, spec.md ✅

**Status**: All tasks completed ✅

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可並行執行（不同檔案、無相依）
- **[Story]**: 對應 spec.md 中的 User Story（US1/US2/US3）

---

## Phase 1 — ThemeProvider 基礎

**Purpose**: 建立全域主題狀態管理，讓 NavBar 與 RAG 元件可消費

- [X] T001 [US1,US2] 建立 `frontend/lib/providers/theme-provider.tsx`：定義 `ThemeMode`（`'light'|'dark'|'auto'`）與 `ResolvedTheme`，實作 `ThemeProvider` component（localStorage 初始化、`matchMedia` 監聽、`applyTheme` 操作 `document.documentElement.classList`）與 `useTheme()` hook
- [X] T002 [P] [US1,US2] 更新 `frontend/lib/providers/index.tsx`：將 `ThemeProvider` 加為最外層 wrapper，export `useTheme`
- [X] T003 [P] [US2] 更新 `frontend/app/layout.tsx`：在 `<html>` 加 `suppressHydrationWarning` 防止 SSR hydration mismatch

**Checkpoint**: `useTheme()` 可在任意 client component 使用，`localStorage` 讀寫正確，`.dark` class 正確切換

---

## Phase 2 — NavBar Toggle Button

**Purpose**: 提供使用者操作入口

- [X] T004 [US1] 更新 `frontend/components/features/navigation/nav-bar.tsx`：import `Sun`, `Moon`, `Monitor`（lucide-react）與 `useTheme`；新增 theme toggle `<button>`（onClick: `cycleMode`，icon 依 `mode` 切換，`cursor-pointer`，`Tooltip` 顯示模式名稱），置於 GitHub icon 左側

**Checkpoint**: 點擊按鈕三次完整循環 light → dark → auto → light，icon 及 `.dark` class 正確切換

---

## Phase 3 — RAG 元件主題整合

**Purpose**: 讓 chatbot UI 元件隨全域 theme 更新

- [X] T005 [US3] 更新 `frontend/components/features/chat/FloatingChatbotWrapper.tsx`：
  - 從 `useTheme()` 取 `mode`（非 `theme`）
  - 傳 `theme={mode}` prop 給 `<FloatingChatbotPanel>`（自作浮動 UI，非外部 `ChatbotPlugin`）
- [X] T006 [P] [US3] 更新 `frontend/components/features/chat/InlineQABarWrapper.tsx`：
  - 從 `useTheme()` 取 `mode`
  - 直接傳 `theme={mode}` prop 給 `<AgentInput>`

**Checkpoint**: 切換至 dark → 開啟 FloatingChatbot → 聊天視窗呈現深色 `--cp-surface` token

---

## Summary

| Phase | Tasks | Status |
|-------|-------|--------|
| Phase 1 — ThemeProvider | T001, T002, T003 | ✅ Done |
| Phase 2 — NavBar Toggle | T004 | ✅ Done |
| Phase 3 — RAG 整合 | T005, T006 | ✅ Done |

**Total**: 6 tasks, 6 completed
