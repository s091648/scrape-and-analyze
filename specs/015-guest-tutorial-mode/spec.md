# Feature Specification: Guest Tutorial Mode & Feature Spotlight

**Feature Branch**: `015-guest-tutorial-mode`

**Created**: 2026-06-29

**Updated**: 2026-07-05 (aligned spec with shipped implementation: 10-step Guest Onboarding Tour, real `feature-chat-2026-07` Feature Spotlight Tour, member-variant CTA-step copy, and the guest-only "Stay in Guest Mode" button)

**Status**: Draft

**Input**: 在 guest mode 時新增一個 tutorial mode，加上一個類似於 stepper 的東西，一步一步地告訴使用者如何操作。後續追加需求：教學呈現方式改為「灰色 overlay + 對目標元素挖空 highlight + 頁面導覽 + 貼齊元素的說明對話框」，並擴充為所有使用者在新功能上線時都能看到對應的功能導覽（feature spotlight），且已讀狀態需要持久化。

## Background

Guest Mode（spec 009）已實作完成：使用者可從 `/login` 點擊「以訪客身份繼續」進入 demo 狀態，看到真實第一頁文章，但功能受限。

首次進入 guest mode 的使用者面對一個陌生的介面，不清楚哪些功能可以操作、各頁面的用途、如何從 demo 升級為正式帳號。同時，隨著產品持續上線新功能，既有的登入使用者（member）也需要一個機制被動得知新功能的存在，而不是每次都要看 Release Notes 才知道。

本功能因此涵蓋兩種概念上不同、但共用同一套 UI 機制的導覽（統稱 **Tutorial Tour**）：

1. **Guest Onboarding Tour**：guest mode 啟動時，顯示一個多步驟的引導，依序導覽 Articles、Graph 等核心頁面並在 NavBar 上 highlight 對應項目，最後提供登入/註冊 CTA。
2. **Feature Spotlight Tour**：新功能上線後，guest 與已登入 member（不含純未登入 paywall 使用者）第一次造訪該功能所在頁面時，自動 highlight 該功能的 UI 元素並顯示說明，看過（或關閉）後不再重複出現。

兩種 Tour 都以「灰色遮罩 + 對目標元素挖空 highlight + 貼齊該元素的說明對話框（stepper：上一步/下一步/跳過/步驟指示）」呈現；若目標元素不在使用者當前頁面，Guest Onboarding Tour 會主動導覽過去，Feature Spotlight Tour 則只在使用者剛好造訪該頁面時才出現（不強制跳頁）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 首次進入 Guest Mode 自動顯示導覽 (Priority: P1)

使用者從登入頁點擊「以訪客身份繼續」進入 guest mode 時，自動開始 Guest Onboarding Tour：遮罩覆蓋畫面、依序 highlight 首頁、NavBar 上的 Articles、Graph 連結，並在對應步驟自動導覽到該頁面，最後 highlight 登入按鈕並提供 CTA。

**Why this priority**: Tutorial 的核心入口與核心價值；提供即時的操作脈絡，讓 demo 不再是盲目探索。

**Independent Test**: 進入 `/login` → 點擊「以訪客身份繼續」→ 畫面出現遮罩，第一步（Welcome，置中卡片、無 highlight）顯示。可獨立驗證，不依賴後續任何步驟完成。

**Acceptance Scenarios**:

1. **Given** 使用者在 `/login` 頁面點擊「以訪客身份繼續」，**When** guest mode 啟動，**Then** 導覽自動開始，顯示第一個步驟（Welcome，置中卡片，無 highlight）
2. **Given** 導覽已開啟且目前在 Welcome 步驟，**When** 使用者點擊「Next」，**Then** 頁面導覽至 `/articles`、遮罩挖空 highlight NavBar 上的 Articles 連結、下方顯示對應說明卡片，步驟指示器更新
3. **Given** 導覽進行至 Graph 步驟，**When** 使用者點擊「Back」，**Then** 頁面導覽回 `/articles`，highlight 回到 Articles 連結
4. **Given** 導覽已開啟，**When** 使用者點擊「X」或「Skip」，**Then** 導覽關閉，不會再自動彈出（同一次 guest mode session 內）
5. **Given** 使用者完成所有步驟並點擊「Sign In」或「Register」，**When** 最後一步完成，**Then** 導覽關閉並導向對應頁面
6. **Given** 使用者重新整理頁面（仍在 guest mode，且尚未關閉過本次分頁 session 內的導覽），**When** 頁面重載，**Then** Guest Onboarding Tour **再次**自動顯示；**若已在本次分頁 session 內關閉過**，**Then** 重新整理不再自動顯示（見 FR-001、FR-012）
7. **Given** highlight 目標元素（例如 Articles 連結）此刻正被 highlight，**When** 使用者嘗試點擊該元素，**Then** 點擊被攔截（僅視覺標示，不可互動）

---

### User Story 2 - 使用者可手動重新開啟 Guest Onboarding Tour (Priority: P2)

Guest 使用者與已登入 member 在導覽結束後可以透過 NavBar 上的 HelpCircle icon 重新開啟 Guest Onboarding Tour，從第一步開始。

**Why this priority**: Tutorial 跳過後可能想重新瀏覽；主動再觸發的能力讓教學不是一次性消費。

**Independent Test**: 在 guest mode 下關閉導覽 → 點擊 NavBar「?」icon → 導覽重新開啟，可獨立驗證。

**Acceptance Scenarios**:

1. **Given** 使用者處於 guest mode 或已登入，且導覽已關閉，**When** 使用者點擊 NavBar 上的 HelpCircle icon，**Then** Guest Onboarding Tour 重新開啟，從第一步（Welcome）開始，且會導覽回首頁
2. **Given** 導覽重新開啟，**When** 使用者瀏覽步驟，**Then** 所有步驟正常運作（導航、highlight、關閉皆可用）
3. **Given** 使用者**非** guest mode 且未登入（paywall 狀態），**When** 觀察 NavBar，**Then** HelpCircle 入口不顯示

---

### User Story 3 - Tutorial 步驟涵蓋核心功能頁 (Priority: P2)

Guest Onboarding Tour 的步驟清楚說明 Welcome、Articles、Graph、以及升級 CTA，讓使用者對整個 demo 範圍有完整認知，且每個步驟都清楚 highlight 對應的具體 UI 元素。

**Why this priority**: Tutorial 的內容品質直接影響使用者轉換率與 demo 體驗；步驟設計必須覆蓋所有 guest-accessible 功能並精準指向對應元素。

**Independent Test**: 開啟導覽 → 逐步瀏覽所有步驟 → 確認每步都對應一個具體的頁面／UI 元素，且最後一步 highlight 登入按鈕並提供 CTA。

**Acceptance Scenarios**:

1. **Given** 導覽開啟，**When** 使用者瀏覽所有步驟，**Then** 步驟依序為：(1) Welcome/概覽（無 highlight）、(2) Articles（highlight NavBar Articles 連結）、(3) Graph（highlight NavBar Graph 連結）、(4) Tags（highlight NavBar Tags 連結）、(5) 語言切換（highlight NavBar 語言選單）、(6) 淺色/深色模式（highlight NavBar 主題按鈕）、(7) GitHub 原始碼（highlight NavBar GitHub 連結）、(8) 規格文件（highlight NavBar Docs 連結）、(9) Release Notes（highlight NavBar Release Notes 按鈕）、(10) 登入 CTA（highlight NavBar 登入按鈕）
2. **Given** 導覽的最後一步且使用者為 guest，**When** 顯示，**Then** 提供「維持訪客模式」、「Sign In」與「Register」按鈕；點擊「Sign In」/「Register」導向對應頁面並關閉導覽，點擊「維持訪客模式」僅關閉導覽、不導向任何頁面
2a. **Given** 導覽的最後一步且使用者為已登入 member（透過 HelpCircle 重新開啟），**When** 顯示，**Then** 改為顯示單一「Done」按鈕（不顯示 Sign In/Register/維持訪客模式），且該步驟文案為 member 專用版本
3. **Given** 導覽中的任一步驟，**When** 使用者點擊「Back」，**Then** 回到前一步並同步導覽回對應頁面（第一步的 Back 不顯示或 disabled）
4. **Given** 導覽所有步驟，**When** 任意步驟顯示時，**Then** 步驟進度（如 "Step 2 of 4"）可視
5. **Given** highlight 目標元素因故（例如尚未渲染完成）在 3 秒內找不到，**When** 逾時，**Then** 該步驟自動退回置中卡片顯示（不卡住導覽流程）

---

### User Story 4 - 多語系支援 (Priority: P3)

Tutorial 內容（含 Guest Onboarding 與 Feature Spotlight）支援中英雙語，隨 app 的語系設定自動切換。

**Why this priority**: 整個 app 已有 i18n，tutorial 必須一致；但這是錦上添花，不影響 MVP。

**Independent Test**: 切換語言到 zh-TW → 進入 guest mode → 導覽以中文顯示所有步驟，可獨立驗證。

**Acceptance Scenarios**:

1. **Given** app 語系為 `zh-TW`，**When** 導覽開啟，**Then** 所有步驟標題、描述、按鈕文字均以繁體中文顯示
2. **Given** app 語系為 `en`，**When** 導覽開啟，**Then** 所有內容以英文顯示
3. **Given** 導覽開啟期間語系切換，**When** 語言變更，**Then** 內容即時更新（利用現有 i18n context）

---

### User Story 5 - 新功能上線時自動向所有使用者顯示 Feature Spotlight (Priority: P2)

新功能上線後，guest 與已登入 member 第一次造訪該功能所在頁面時，自動 highlight 該功能的 UI 元素並顯示說明；使用者關閉後（不論走完、Skip 或按 X）該功能不再重複提示。

**Why this priority**: 讓既有使用者（尤其是不會主動看 Release Notes 的 member）也能被動發現新功能，是 Guest Onboarding Tour 之外這次擴充的核心價值。

**Independent Test**: 在 `tutorial-registry.ts` 註冊一個測試用 spotlight tour（目標頁面 `/articles`）→ 以尚未看過該 tour 的使用者身份造訪 `/articles` → 自動出現 highlight → 關閉後重新整理頁面 → 不再出現。可獨立驗證，不依賴 Guest Onboarding Tour。

**Acceptance Scenarios**:

1. **Given** 使用者（guest 或 member）尚未看過某個 Feature Spotlight Tour，**When** 使用者造訪該 tour 目標頁面，**Then** 自動顯示 highlight + 說明卡片，不強制跳轉離開使用者原本所在的頁面
2. **Given** 使用者已看過（走完/Skip/關閉）某個 Feature Spotlight Tour，**When** 使用者再次造訪同一頁面，**Then** 不再自動顯示該 tour
3. **Given** 純未登入的 paywall 使用者，**When** 造訪任何頁面，**Then** 不會看到任何 Feature Spotlight Tour
4. **Given** Guest Onboarding Tour 正在顯示中，**When** 使用者造訪的頁面同時符合某個 Feature Spotlight Tour 的觸發條件，**Then** Feature Spotlight Tour 不會同時彈出（同一時間只顯示一個 tour）
5. **Given** 一個 Feature Spotlight Tour 的所有步驟，**When** 定義該 tour，**Then** 所有步驟必須指向同一個 `route`（不可跨頁）

---

### Edge Cases

- 使用者在導覽開啟時直接關閉瀏覽器分頁 → sessionStorage（含 `guest_mode` 與 `tutorial_onboarding_dismissed`）清除，下次（新分頁）進入 guest mode 時 Guest Onboarding Tour 重新顯示（符合預期）；Feature Spotlight 的已讀狀態存 localStorage，不受分頁關閉影響
- 導覽開啟時螢幕尺寸極小（mobile width，< 768px）→ 不進行 highlight 定位計算，所有步驟一律退回置中卡片顯示，不超出視窗
- Guest mode 被外部事件清除（如登入完成）→ Guest Onboarding Tour 立即關閉
- 使用者快速連按「Next」→ 不應出現重複渲染或步驟跳過問題
- Highlight 目標元素在畫面內捲動（非 fixed 定位）→ highlight 框需隨捲動即時跟隨
- Highlight 目標元素因非同步載入尚未掛載 → 最多輪詢等待 3 秒，逾時則該步驟退回置中卡片

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系統 MUST 在使用者進入 guest mode 時自動開始 Guest Onboarding Tour，除非該分頁 session 內已被關閉過（見 FR-012 的 `sessionStorage` 已讀狀態）
- **FR-002**: 系統 MUST NOT 在 member（已登入）的任何頁面載入時自動顯示 Guest Onboarding Tour；member 只能透過 HelpCircle 手動開啟
- **FR-003**: Guest Onboarding Tour MUST 包含至少 4 個步驟：Welcome（無 highlight）、Articles（highlight NavBar 連結）、Graph（highlight NavBar 連結）、Sign Up CTA（highlight 登入按鈕）。目前實作共 10 個步驟，額外涵蓋 Tags、語言切換、淺色/深色模式、GitHub 原始碼、規格文件、Release Notes，皆 highlight 對應的 NavBar 元素
- **FR-004**: 使用者 MUST 能夠透過「X」或「Skip」在任意步驟關閉導覽
- **FR-005**: 導覽 MUST 顯示當前步驟指示（如進度條或 dot indicators）
- **FR-006**: 導覽 MUST 提供「Back」（第一步除外）與「Next」導航按鈕；切換步驟時若該步驟綁定的 `route` 與目前頁面不同，系統 MUST 自動導覽過去
- **FR-007**: 最後一步 MUST 提供「Sign In」與「Register」CTA 按鈕
- **FR-007a**: 當使用者以 guest mode 身份瀏覽最後一步時，系統 MUST 額外提供「維持訪客模式」(Stay in Guest Mode) 按鈕；點擊後僅關閉導覽，不導向登入/註冊頁面、不強制登出 guest mode
- **FR-008**: guest mode 及已登入 member 下 NavBar MUST 提供可手動重開 Guest Onboarding Tour 的入口（HelpCircle icon）
- **FR-008a**: 已登入 member 透過 HelpCircle 重新開啟 Guest Onboarding Tour 時，Welcome 步驟與最後一步 MUST 顯示 member 專用文案（`titleKeyMember`/`descriptionKeyMember`），且最後一步 MUST NOT 顯示「Sign In」/「Register」/「維持訪客模式」CTA，改為顯示單一「Done」按鈕
- **FR-009**: 純未登入使用者（paywall 狀態）MUST NOT 看到任何 Tour（Guest Onboarding 或 Feature Spotlight）的入口或內容
- **FR-010**: Tutorial 所有文字內容 MUST 支援 i18n（en + zh-TW）
- **FR-011**: 導覽 MUST 在 guest mode 被清除（如登入完成）時自動關閉
- **FR-012**: 系統 MUST 使用 `localStorage`（key: `tutorial_seen_tours`，JSON `string[]`）記錄使用者已看過／已關閉的 Feature Spotlight Tour id；Guest Onboarding Tour 的自動觸發不依賴此清單，而是使用獨立的 `sessionStorage`（key: `tutorial_onboarding_dismissed`）記錄「本次分頁 session 是否已關閉過」——分頁關閉、或使用者離開再重新進入 guest mode 時清除，因此每次「新的 guest mode session」都會重新顯示，但同一 session 內 refresh 不會重複彈出
- **FR-013**: 被 highlight 的目標元素 MUST 僅作視覺標示，期間 MUST NOT 可被點擊互動（遮罩需攔截該區域的點擊事件）
- **FR-014**: 系統 MUST 提供通用的 highlight 定位機制，支援任意頁面內容元素（含會隨頁面捲動、換頁/非同步載入後才掛載的元素），而非僅限於常駐的 NavBar 元素
- **FR-015**: 若 highlight 目標元素在 3 秒內未能於 DOM 中找到，系統 MUST 將該步驟自動退回置中卡片顯示，不得阻塞導覽流程
- **FR-016**: 於視窗寬度 < 768px 時，系統 MUST 停用 highlight 定位計算，所有步驟一律以置中卡片顯示
- **FR-017**: Feature Spotlight Tour MUST 僅在使用者（guest 或 member）造訪其目標頁面、且該 tour id 不在 `tutorial_seen_tours` 清單中時自動顯示；MUST NOT 強制導覽使用者離開目前頁面
- **FR-018**: 使用者以任何方式關閉一個 Feature Spotlight Tour（走完、Skip、或按 X）後，系統 MUST 將該 tour id 寫入 `tutorial_seen_tours`
- **FR-019**: 同一時間 MUST 最多只顯示一個 Tour（Guest Onboarding 與 Feature Spotlight 不可同時顯示）
- **FR-020**: 新增一個 Feature Spotlight Tour MUST 只需要在 tutorial registry 中新增一筆設定（步驟內容、目標元素 id、目標頁面），不需修改 Tour 呈現邏輯本身

### Key Entities

- **TutorialStep**: 單一步驟，含 `id`、`titleKey`/`descriptionKey`（i18n key）、`icon`（可選）、`targetId`（可選，DOM id，未提供則置中顯示）、`route`（該步驟對應頁面路徑）、`isCta`（可選，標記為登入/註冊 CTA 步驟）、`titleKeyMember`/`descriptionKeyMember`（可選，member 重新開啟導覽時取代 `titleKey`/`descriptionKey` 的專用文案）
- **TutorialTour**: 一組 Tour，含 `id`（唯一識別）、`kind`（`"onboarding"` 或 `"spotlight"`）、`steps: TutorialStep[]`；`spotlight` 類型的所有 step 必須共用同一個 `route`
- **TutorialState**: 執行期狀態 `{ isTutorialOpen: boolean; activeTourId: string | null; tutorialStep: number }`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 首次進入 guest mode 後，Guest Onboarding Tour 在 500ms 內自動開始
- **SC-002**: 使用者能在 60 秒內完整瀏覽所有 Guest Onboarding 步驟並抵達 CTA
- **SC-003**: 所有步驟均可透過鍵盤操作（Tab 導航、Enter 觸發按鈕、Escape 關閉）
- **SC-004**: Tutorial 不影響現有 guest mode 功能的任何迴歸（Playwright E2E 全通）
- **SC-005**: 中英雙語內容均正確顯示，無遺漏 i18n key
- **SC-006**: Highlight 框與目標元素的實際畫面位置誤差 < 2px（含視窗縮放/捲動後重新計算）
- **SC-007**: 新增一個 Feature Spotlight Tour 平均只需修改一個檔案（tutorial registry）

## Assumptions

- Tutorial 為純前端功能，不需要後端 API 變更；已讀狀態不落地到資料庫（guest 使用者本來就沒有帳號，member 換裝置頂多重看一次，不值得為此開後端戰線；詳見決策記錄於 `plan.md`）。Feature Spotlight 用 `localStorage`（跨分頁、永久）；Guest Onboarding 用 `sessionStorage`（僅限本次分頁 session，關閉分頁或重新進入 guest mode 即清除）
- 現有 Shadcn/UI `Popover`（`PopoverAnchor` + `virtualRef`）與 Tailwind box-shadow 技巧足以實作 highlight + 定位；不引入第三方 onboarding library（如 react-joyride、driver.js）
- Mobile（< 768px）一律退回置中卡片顯示，不做響應式 spotlight 定位
- 本 feature 不改動 guest mode 的 `sessionStorage` key（`guest_mode`）
- 首個 Feature Spotlight Tour 的實際內容已於本次範圍內一併完成：`feature-chat-2026-07`（pin-to-chat 與開啟 AI 對話面板，2 個步驟，皆位於 `/articles`）作為 registry 機制的第一個真實案例；後續新增 Feature Spotlight Tour 仍只需在 registry 新增一筆設定，不需修改 Tour 呈現邏輯
