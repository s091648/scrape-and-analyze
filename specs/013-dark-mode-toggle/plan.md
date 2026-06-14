# Implementation Plan: Light / Dark / Auto Theme Toggle

**Branch**: `012-rag-chatbot-integration` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/013-dark-mode-toggle/spec.md`

---

## Summary

在 Next.js 16 + Tailwind v4 的 frontend 中實作三段式主題切換（light / dark / auto），透過 React Context (`ThemeProvider`) 管理全域狀態，NavBar 提供循環切換按鈕，`@s091648/chatbot-plugin-ui` 元件透過 `theme` prop 接收模式。

---

## Technical Context

**Language/Version**: TypeScript 5, React 19, Next.js 16 (App Router)

**Primary Dependencies**: Tailwind CSS v4（class-based dark mode）, lucide-react（icon）, `@s091648/chatbot-plugin-ui`

**Storage**: `localStorage`（key: `app-theme-mode`）

**Testing**: Vitest（unit），Playwright（E2E）

**Target Platform**: Web browser（SSR + CSR）

**Performance Goals**: 主題切換無 layout shift，無閃爍

**Constraints**: SSR 相容（Next.js App Router），hydration mismatch 抑制

**Scale/Scope**: 單一 frontend 應用，全域共享一個 ThemeContext

---

## Constitution Check

- **§I DDD**: 不涉及 scraper / backend domain，N/A。
- **§II Atomic Frontend Architecture**: `ThemeProvider` 屬於 Context provider，置於 `lib/providers/`（`AppProviders` 層）而非 `components/providers/`（constitution 允許 providers 在 layout 層包覆）。`useTheme()` 為 hook，不是 component，不需 Storybook story。NavBar 為既有 feature component，theme 邏輯以 hook 方式注入，無需新元件。✅
- **§III Test Discipline**: 純 frontend 功能，無 Python 測試要求。若新增 unit test 需用 Vitest。此功能小型改動，現有整合測試覆蓋 NavBar 操作，theme 切換無需獨立 E2E test。✅

---

## Architecture

### ThemeProvider (`lib/providers/theme-provider.tsx`)

```
ThemeProvider
  ├── state: mode (ThemeMode: 'light'|'dark'|'auto')  ← 使用者選擇
  ├── state: theme (ResolvedTheme: 'light'|'dark')     ← 實際套用值
  ├── effect[]: 讀取 localStorage → 初始化 mode + theme
  ├── effect[mode]: 監聽 matchMedia 變化（僅 auto 時有效）
  ├── setMode(newMode): 更新 state + localStorage + document.documentElement.classList
  ├── cycleMode(): light → dark → auto → light
  └── context: { mode, theme, setMode, cycleMode }
```

### Provider 層級（`lib/providers/index.tsx`）

```
ThemeProvider          ← 最外層（先於 Session，確保 theme 在 SSR hydrate 前就位）
  └── SessionProviderWrapper
        └── TopicProvider
              └── I18nProvider
                    └── GuestModeProvider
                          └── {children}
```

### Tailwind v4 Dark Mode

`globals.css`：
```css
@custom-variant dark (&:is(.dark *));
```
`ThemeProvider.applyTheme()` 操作 `document.documentElement.classList.toggle('dark', resolved === 'dark')`。

### RAG 元件主題整合

```
useTheme() → { mode }
     ↓
<ChatbotPlugin theme={mode} />   ← 直接傳 prop，讓元件自身設 data-chatbot-theme
<AgentInput theme={mode} />
```

**關鍵細節**：不可在外層 wrapper div 設 `data-chatbot-theme`，否則元件自身的 default `data-chatbot-theme="auto"` 會透過 CSS 覆蓋外層，導致主題失效。

### NavBar Toggle

```tsx
const { mode, cycleMode } = useTheme()
const ThemeIcon = mode === 'light' ? Sun : mode === 'dark' ? Moon : Monitor
// 按鈕：onClick={cycleMode}, cursor-pointer, Tooltip 顯示模式名
```

---

## Data Flow

```
使用者點擊 NavBar toggle
  → cycleMode()
  → setMode(nextMode)
    → setModeState(nextMode)          // React re-render
    → setTheme(resolved)              // React re-render
    → localStorage.setItem(...)       // 持久化
    → document.documentElement.classList.toggle('dark', ...)  // CSS
  → 所有 useTheme() consumers re-render
    → NavBar: icon 切換
    → FloatingChatbotWrapper: theme prop 更新 → chatbot data-chatbot-theme 更新
    → InlineQABarWrapper: 同上
```

---

## Phases

### Phase 1 — ThemeProvider 基礎

建立 `lib/providers/theme-provider.tsx`，整合至 `AppProviders`，加 `suppressHydrationWarning`。

### Phase 2 — NavBar Toggle

在 NavBar 右側 icon 區加入 theme toggle button（Sun/Moon/Monitor icon，Tooltip，cursor-pointer）。

### Phase 3 — RAG 元件整合

`FloatingChatbotWrapper` 與 `InlineQABarWrapper` 改用 `mode` prop 傳入 chatbot 元件，移除 wrapper div 的 `data-chatbot-theme`。

---

## Key Files

| File | Role |
|------|------|
| `frontend/lib/providers/theme-provider.tsx` | 核心 Context + hook |
| `frontend/lib/providers/index.tsx` | ThemeProvider 加入 AppProviders；export useTheme |
| `frontend/app/layout.tsx` | `<html suppressHydrationWarning>` |
| `frontend/components/features/navigation/nav-bar.tsx` | Toggle button |
| `frontend/components/features/rag/FloatingChatbotWrapper.tsx` | theme prop 傳遞 |
| `frontend/components/features/rag/InlineQABarWrapper.tsx` | theme prop 傳遞 |
