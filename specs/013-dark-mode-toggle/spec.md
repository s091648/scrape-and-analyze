# Feature Specification: Light / Dark / Auto Theme Toggle

**Feature Branch**: `013-dark-mode-toggle`

**Created**: 2026-06-14

**Status**: Implemented

**Input**: User description: "在 NavBar 加一個切換 light / dark / auto mode 的 icon，點擊依序切換，icon 隨之改變。RAG 元件隨 theme 更新。"

---

## User Scenarios & Testing

### User Story 1 — Theme Cycle Toggle (Priority: P1)

使用者可在 NavBar 右側點擊一個 icon，依序在 Light → Dark → Auto 三種模式之間切換，整個應用程式的配色立即跟著更新。

**Why this priority**: 最核心的 UX 行為 — 無此行為則其他 story 無意義。

**Independent Test**: 開啟任意頁面 → 點擊 NavBar 的主題 icon 三次 → 畫面依序切換為深色、自動、淺色。

**Acceptance Scenarios**:

1. **Given** 使用者在任意頁面，**When** 點擊 NavBar theme icon，**Then** 依序切換 `light → dark → auto → light`，icon 分別顯示 `Sun / Moon / Monitor`。
2. **Given** 目前為 `light` 模式，**When** 切換至 `dark`，**Then** `<html>` 加上 `.dark` class，Tailwind dark 樣式生效。
3. **Given** 目前為 `dark` 模式，**When** 切換至 `auto`，**Then** `.dark` class 依系統 `prefers-color-scheme` 決定。
4. **Given** Tooltip hover 在 theme icon 上，**Then** 顯示目前模式名稱（Light / Dark / Auto）。

---

### User Story 2 — 偏好持久化 (Priority: P2)

使用者選擇的主題模式在重整頁面或重新開啟瀏覽器後仍維持。

**Why this priority**: 若每次重整都回到預設，體驗大打折扣。

**Independent Test**: 切換至 `dark` → 重整頁面 → 應用程式仍為深色。

**Acceptance Scenarios**:

1. **Given** 使用者切換至 `dark`，**When** 重整頁面，**Then** 仍為 dark 模式且不閃爍 (hydration)。
2. **Given** 使用者切換至 `auto`，**When** 重整頁面，**Then** 立即跟隨系統配色，不閃爍。
3. **Given** 無儲存記錄（首次訪問），**Then** 預設為 `auto` 模式。

---

### User Story 3 — RAG 元件同步更新 (Priority: P3)

`FloatingChatbotWrapper` 與 `InlineQABarWrapper` 的 UI 隨全域 theme 同步更新，不需使用者額外操作。

**Why this priority**: RAG 元件是獨立的 npm 套件，需明確整合主題系統。

**Independent Test**: 切換至 `dark` → 展開 ChatbotPlugin FAB → 聊天視窗為深色配色。

**Acceptance Scenarios**:

1. **Given** 全域為 `dark` 模式，**When** 開啟 FloatingChatbot，**Then** 聊天視窗顯示深色 (`--cp-surface` 使用 dark token)。
2. **Given** 全域為 `auto` 且系統為深色，**When** 使用 InlineQABar，**Then** 元件顯示深色（透過 `@media prefers-color-scheme`）。
3. **Given** 切換 theme，**When** RAG 元件已掛載，**Then** 立即更新，無需重新掛載。

---

## Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-001 | NavBar 需有 theme toggle 按鈕，位於右側 icon 區（GitHub icon 左側）。|
| FR-002 | 點擊循環切換 `light → dark → auto → light`。|
| FR-003 | 按鈕 icon 依模式顯示：`Sun`（light）、`Moon`（dark）、`Monitor`（auto）。|
| FR-004 | `light` / `dark` 套用至 `<html>` `.dark` class（Tailwind v4 class-based dark mode）。|
| FR-005 | `auto` 模式跟隨 `prefers-color-scheme`，切換系統主題時即時反應。|
| FR-006 | 模式儲存至 `localStorage`（key: `app-theme-mode`），持久化跨 session。|
| FR-007 | SSR 不閃爍：`<html suppressHydrationWarning>`。|
| FR-008 | `FloatingChatbotWrapper` / `InlineQABarWrapper` 透過 `theme` prop（非 wrapper div）傳遞模式至 chatbot 元件。|
| FR-009 | Theme toggle icon 的 cursor 為 `pointer`。|
| FR-010 | Tooltip hover 顯示目前模式名稱。|

---

## Success Criteria

| ID | Criterion |
|----|-----------|
| SC-001 | Tailwind dark 樣式（`dark:` prefix）在切換至 `dark` 或 `auto`（系統深色）時正確生效。|
| SC-002 | 頁面重整後無白閃（hydration mismatch 抑制）。|
| SC-003 | RAG 元件 `data-chatbot-theme` 屬性與全域 `mode` 同步。|
| SC-004 | `auto` 模式下變更系統主題後應用程式即時更新（無需重整）。|

---

## Edge Cases

- **SSR Hydration Mismatch**: 伺服器端無法得知 `localStorage`，初始渲染 `theme='light'`（useState default），client mount 後讀取正確值。透過 `suppressHydrationWarning` 抑制 React mismatch 警告。
- **`data-chatbot-theme` CSS 覆蓋問題**: chatbot 元件自身 root 設有 `data-chatbot-theme`（default `'auto'`），若外層 wrapper div 也設同屬性，內層覆蓋外層。解法：直接透過 `theme` prop 傳入，讓元件自身設正確值。
- **`auto` + 系統切換**: `useEffect` 監聽 `matchMedia('prefers-color-scheme: dark').addEventListener('change', ...)` 即時更新，只在 `mode === 'auto'` 時啟用。
- **`mode` vs `theme` 語義**: `mode` 是使用者選擇（含 `auto`），`theme` 是已解析的實際值（`'light'|'dark'`）。RAG 元件接受 `'light'|'dark'|'auto'`，故傳 `mode` 而非 `theme`。
