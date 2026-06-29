# Feature Specification: Guest Tutorial Mode

**Feature Branch**: `015-guest-tutorial-mode`

**Created**: 2026-06-29

**Status**: Draft

**Input**: 在 guest mode 時新增一個 tutorial mode，加上一個類似於 stepper 的東西，一步一步地告訴使用者如何操作。

## Background

Guest Mode（spec 009）已實作完成：使用者可從 `/login` 點擊「以訪客身份繼續」進入 demo 狀態，看到真實第一頁文章，但功能受限。

然而，首次進入 guest mode 的使用者面對一個陌生的介面，不清楚：
- 哪些功能可以操作
- 各頁面的用途（home vs graph vs tags）
- 如何從 demo 升級為正式帳號

本功能在 guest mode 啟動時，顯示一個 **步驟式引導（Tutorial Stepper）**，以 Modal Overlay 呈現，一步一步說明 guest 可以做什麼，最後提供 CTA 引導登入或註冊。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 首次進入 Guest Mode 自動顯示教學引導 (Priority: P1)

使用者從登入頁點擊「以訪客身份繼續」進入 guest mode 時，自動彈出一個步驟式 Tutorial Modal，說明 guest mode 的功能範圍與操作方式，使用者可逐步閱讀或直接關閉。

**Why this priority**: Tutorial 的核心入口與核心價值；提供即時的操作脈絡，讓 demo 不再是盲目探索。

**Independent Test**: 進入 `/login` → 點擊「以訪客身份繼續」→ Tutorial Modal 自動彈出，顯示第一步。可獨立驗證，不依賴後續任何步驟完成。

**Acceptance Scenarios**:

1. **Given** 使用者在 `/login` 頁面點擊「以訪客身份繼續」，**When** guest mode 啟動，**Then** Tutorial Modal 自動出現，顯示第一個步驟（Welcome）
2. **Given** Tutorial Modal 已開啟，**When** 使用者點擊「Next」，**Then** 進入下一個步驟，步驟指示器（stepper dots / progress）更新
3. **Given** Tutorial Modal 已開啟，**When** 使用者點擊「X」或「Skip」，**Then** Modal 關閉，不會再自動彈出（同一 session 內）
4. **Given** 使用者完成所有步驟並點擊「Get Started」，**When** 最後一步完成，**Then** Modal 關閉，使用者留在主頁
5. **Given** 使用者重新整理頁面（仍在 guest mode），**When** 頁面重載，**Then** Tutorial Modal **再次**自動顯示（guest mode 每次都顯示 tutorial）

---

### User Story 2 - 使用者可手動重新開啟教學引導 (Priority: P2)

Guest 使用者在 tutorial 結束後可以透過某個入口（例如 NavBar 上的 Help / Tutorial 按鈕或 Banner 連結）重新開啟 Tutorial Modal，重新瀏覽各步驟。

**Why this priority**: Tutorial 跳過後可能想重新瀏覽；主動再觸發的能力讓教學不是一次性消費。

**Independent Test**: 在 guest mode 下關閉 Tutorial → 點擊 NavBar「?」icon 或 banner 連結 → Tutorial Modal 重新開啟，可獨立驗證。

**Acceptance Scenarios**:

1. **Given** 使用者處於 guest mode 且 tutorial 已關閉，**When** 使用者點擊 NavBar 上的 Tutorial 入口（icon 或連結），**Then** Tutorial Modal 重新開啟，從第一步開始
2. **Given** Tutorial 重新開啟，**When** 使用者瀏覽步驟，**Then** 所有步驟正常運作（導航、關閉皆可用）
3. **Given** 使用者**非** guest mode（已登入或未登入），**When** 觀察 NavBar，**Then** Tutorial 入口不顯示

---

### User Story 3 - Tutorial 步驟涵蓋核心功能頁 (Priority: P2)

Tutorial 的步驟清楚說明 home（文章列表）、graph（知識圖譜）、guest 限制、以及升級 CTA，讓使用者對整個 demo 範圍有完整認知。

**Why this priority**: Tutorial 的內容品質直接影響使用者轉換率與 demo 體驗；步驟設計必須覆蓋所有 guest-accessible 功能。

**Independent Test**: 開啟 Tutorial → 逐步瀏覽所有步驟 → 確認每步都對應一個具體的 guest 功能點，且最後一步有登入/註冊 CTA。

**Acceptance Scenarios**:

1. **Given** Tutorial Modal 開啟，**When** 使用者瀏覽所有步驟，**Then** 步驟依序包含：(1) Welcome/概覽、(2) 文章列表、(3) 知識圖譜、(4) 登入/註冊 CTA
2. **Given** Tutorial 的最後一步，**When** 顯示，**Then** 提供明確的「Sign In」與「Register」按鈕，點擊後導向對應頁面並關閉 Tutorial
3. **Given** Tutorial 中的任一步驟，**When** 使用者點擊「Back」，**Then** 回到前一步（第一步的 Back 不顯示或 disabled）
4. **Given** Tutorial 所有步驟，**When** 任意步驟顯示時，**Then** 步驟進度（如 "Step 2 of 4"）可視

---

### User Story 4 - 多語系支援 (Priority: P3)

Tutorial 內容支援中英雙語，隨 app 的語系設定自動切換。

**Why this priority**: 整個 app 已有 i18n，tutorial 必須一致；但這是錦上添花，不影響 MVP。

**Independent Test**: 切換語言到 zh-TW → 進入 guest mode → Tutorial Modal 以中文顯示所有步驟，可獨立驗證。

**Acceptance Scenarios**:

1. **Given** app 語系為 `zh-TW`，**When** Tutorial Modal 開啟，**Then** 所有步驟標題、描述、按鈕文字均以繁體中文顯示
2. **Given** app 語系為 `en`，**When** Tutorial Modal 開啟，**Then** 所有內容以英文顯示
3. **Given** Tutorial 開啟期間語系切換，**When** 語言變更，**Then** Modal 內容即時更新（利用現有 i18n context）

---

### Edge Cases

- 使用者在 Tutorial 開啟時直接關閉瀏覽器分頁 → sessionStorage 清除，下次進入 guest mode 時 tutorial 重新顯示（符合預期）
- Tutorial 開啟時螢幕尺寸極小（mobile width）→ Modal 應垂直捲動或自適應，不超出視窗
- Guest mode 被外部事件清除（如登入完成）→ Tutorial 立即關閉
- 使用者快速連按「Next」→ 不應出現重複渲染或步驟跳過問題

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系統 MUST 在使用者每次進入 guest mode 時**無條件**自動顯示 Tutorial Modal（不做任何 storage 檢查）
- **FR-002**: 系統 MUST NOT 在 member（已登入）的任何頁面載入時自動顯示 Tutorial；member 只能透過 HelpCircle 手動開啟
- **FR-003**: Tutorial Modal MUST 包含至少 4 個步驟：Welcome、Articles、Graph、Sign Up CTA
- **FR-004**: 使用者 MUST 能夠透過「X」或「Skip」在任意步驟關閉 Tutorial
- **FR-005**: Tutorial Modal MUST 顯示當前步驟指示（如進度條或 dot indicators）
- **FR-006**: Tutorial MUST 提供「Back」（第一步除外）與「Next」導航按鈕
- **FR-007**: 最後一步 MUST 提供「Sign In」與「Register」CTA 按鈕
- **FR-008**: guest mode 及已登入 member 下 NavBar MUST 提供可手動重開 Tutorial 的入口（HelpCircle icon）
- **FR-009**: 純未登入使用者（paywall 狀態）MUST NOT 看到 Tutorial 入口或 Modal
- **FR-010**: Tutorial 所有文字內容 MUST 支援 i18n（en + zh-TW）
- **FR-011**: Tutorial Modal MUST 在 guest mode 被清除（如登入完成）時自動關閉
- **FR-012**: 系統 MUST 使用 `localStorage` 儲存 per-page tutorial 狀態（`tutorial_seen_pages`），供未來各頁面個別引導使用；全域 tutorial 的自動觸發不依賴此 storage

### Key Entities

- **TutorialStep**: 單一步驟，含 `id`、`titleKey`（i18n key）、`descriptionKey`（i18n key）、`icon`（可選）
- **TutorialState**: `{ isOpen: boolean; currentStep: number; hasSeenTutorial: boolean }`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 首次進入 guest mode 後，Tutorial Modal 在 500ms 內自動彈出
- **SC-002**: 使用者能在 60 秒內完整瀏覽所有步驟並抵達 CTA
- **SC-003**: 所有 4 個步驟均可透過鍵盤操作（Tab 導航、Enter 觸發按鈕、Escape 關閉）
- **SC-004**: Tutorial 不影響現有 guest mode 功能的任何迴歸（Playwright E2E 全通）
- **SC-005**: 中英雙語內容均正確顯示，無遺漏 i18n key

## Assumptions

- Tutorial 為純前端功能，不需要後端 API 變更
- 步驟內容為靜態文字（+ 可選 icon），不需要後端動態載入
- 現有 Shadcn/UI `Dialog` 元件足以實作 Modal 主體；不引入第三方 onboarding library
- Tutorial 僅在 guest mode 下顯示，不適用於已登入使用者或純未登入訪客
- Mobile 響應式屬於 P2（確保不破版），完整 mobile 優化屬 future scope
- 本 feature 不改動 guest mode 的 `sessionStorage` key（`guest_mode`），新增獨立 key（`guest_tutorial_seen`）
