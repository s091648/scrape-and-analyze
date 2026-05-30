# Feature Specification: Guest Mode

**Feature Branch**: `feat/article_id_and_guest`

**Created**: 2026-05-30

**Status**: Draft

**Input**: User description: "在登入頁面新增訪客模式選項，讓使用者可以用 guest 假帳號/狀態做有限度的 demo；訪客能看到真實第一頁文章，但功能受限（無 settings、無翻頁、graph 僅第一頁資料）。"

## Background

目前系統有兩種使用者狀態：已登入（完整功能）和未登入（paywall — 顯示模糊佔位文章 + 鎖定覆蓋層）。

本功能在兩者之間插入第三種狀態：**Guest Mode**。Guest 是使用者在登入頁面主動選擇的 demo 模式，可以看到真實的第一頁文章資料，但功能受到限制。Guest 不是「未登入」，也不是正式帳號，是一個純前端管理的輕量示範 session。

**三種狀態的對應行為**：

| 狀態 | 觸發方式 | 文章資料 | 分頁 | Settings | Graph |
|---|---|---|---|---|---|
| 未登入（純訪客） | 直接造訪（不做任何選擇） | 模糊佔位 + paywall（現有行為，不動） | 無 | 無 icon | 無 |
| Guest Mode | 登入頁點擊「以訪客身份繼續」 | 真實第一頁文章 | 無翻頁 | 無 icon；URL 保護 | 僅第一頁文章範圍 |
| 已登入 | 正式登入 | 完整文章列表 + 分頁 | 完整 | 有 | 完整 |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 從登入頁選擇 Guest Mode 並看到真實第一頁文章 (Priority: P1)

使用者在登入頁面看到「以訪客身份繼續」的選項，點擊後進入主頁，能看到真實的第一頁文章資料（而非模糊佔位），但沒有分頁控制，頁面也清楚標示這是有限度的訪客檢視。

**Why this priority**: Guest Mode 的核心入口與核心價值；沒有這個，後續功能都無意義。

**Independent Test**: 造訪 `/login` → 點擊「以訪客身份繼續」→ 主頁顯示真實第一頁文章（非模糊）且無分頁，可獨立驗證。

**Acceptance Scenarios**:

1. **Given** 使用者造訪 `/login`，**When** 頁面載入，**Then** 除了現有登入選項外，額外顯示「以訪客身份繼續」的選項（按鈕或連結）
2. **Given** 使用者點擊「以訪客身份繼續」，**When** 動作執行，**Then** 使用者被導向主頁，且進入 Guest Mode
3. **Given** 使用者處於 Guest Mode，**When** 主頁載入，**Then** 顯示真實的第一頁文章（非模糊佔位），且無分頁控制元件
4. **Given** 完全未登入的一般訪客（未選擇 Guest Mode），**When** 造訪主頁，**Then** 維持現有 paywall 行為（模糊佔位 + lock overlay），不受影響
5. **Given** 使用者進入 Guest Mode 並重新整理頁面，**When** 頁面重載，**Then** 仍維持 Guest Mode（不退回 paywall）

---

### User Story 2 - Guest 的頁面存取限制與提示 (Priority: P2)

Guest 嘗試透過 URL 進入 `/settings` 等受限頁面時，頁面顯示說明此功能需要帳號的提示，並引導使用者登入或註冊，而非靜默失敗或顯示空白。

**Why this priority**: 補強 Guest Mode 的邊界，確保 demo 體驗完整且不留安全漏洞。

**Independent Test**: 以 Guest Mode 直接造訪 `/settings` → 看到帳號所需提示頁，可獨立驗證。

**Acceptance Scenarios**:

1. **Given** 使用者處於 Guest Mode，**When** 在導覽列中，**Then** settings 圖示不顯示（hidden）
2. **Given** 使用者處於 Guest Mode，**When** 直接透過 URL 造訪 `/settings`，**Then** 顯示說明此功能需要帳號的提示，並提供登入/註冊的連結
3. **Given** Guest 在主頁嘗試切換到第二頁（若有任何方式觸發），**When** 動作被阻擋，**Then** 顯示引導登入的提示，而非靜默失敗

---

### User Story 3 - Guest 的知識圖譜（限縮版本） (Priority: P3)

Guest 進入 `/graph` 時，知識圖譜只呈現第一頁文章對應的節點與連結，並有說明文字提示這是受限的預覽版本。

**Why this priority**: 讓 graph 頁也能 demo，同時保持資料一致性，避免 guest 從圖譜取得超出第一頁的內容。

**Independent Test**: 以 Guest Mode 進入 `/graph` → 節點數量明顯少於完整圖譜，且有受限提示，可獨立驗證。

**Acceptance Scenarios**:

1. **Given** 使用者處於 Guest Mode，**When** 造訪 `/graph`，**Then** 圖譜僅呈現對應第一頁文章（預設約 20 篇）的節點與邊
2. **Given** Guest 的圖譜頁，**When** 頁面顯示，**Then** 有視覺說明告知此為受限的預覽版本，並提供登入連結

---

### User Story 4 - 從 Guest Mode 升級為正式帳號 (Priority: P3)

處於 Guest Mode 的使用者可以在任何時間點選擇登入或註冊，完成後取得完整功能。

**Why this priority**: 完整的使用者旅程，讓 demo 能自然轉化為正式使用者。

**Acceptance Scenarios**:

1. **Given** 使用者處於 Guest Mode，**When** 點擊頁面上任何「登入」或「註冊」連結，**Then** 被導向 `/login` 或 `/register`
2. **Given** Guest 完成正式登入，**When** 登入成功，**Then** Guest Mode 狀態清除，使用者取得完整功能（含分頁、settings 等）

---

### Edge Cases

- Guest Mode 狀態應在頁面重整後維持，但關閉瀏覽器分頁後可自然過期（不需要長期持久化）
- Guest 切換 topic 時，仍只取得該 topic 的第一頁文章
- FilterBar 對 Guest 顯示，但篩選僅作用在第一頁範圍內（不開啟分頁）
- 008 spec 的文章分享連結（`/articles/[id]`）不受 Guest Mode 影響，任何人皆可存取
- Guest 在 Filter 後若結果為零，顯示一般的空狀態提示，不顯示 paywall

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 登入頁 MUST 在現有登入選項之外，額外提供「以訪客身份繼續」選項，不影響現有的 Credentials 和 Google 登入流程
- **FR-002**: 點擊「以訪客身份繼續」後，系統 MUST 將使用者導向主頁並啟動 Guest Mode 狀態
- **FR-003**: Guest Mode 狀態 MUST 在頁面重整後持續存在（於同一瀏覽器 session 內）
- **FR-004**: 完全未登入且未選擇 Guest Mode 的訪客，MUST 維持現有 paywall 行為（不受此功能影響）
- **FR-005**: 處於 Guest Mode 的使用者，MUST 能看到真實的第一頁文章資料（呼叫後端 API，`page=1`），而非模糊佔位
- **FR-006**: Guest Mode 下，系統 MUST 不顯示分頁控制元件（「上一頁」/「下一頁」按鈕）
- **FR-007**: Guest Mode 下，導覽列中的 settings 圖示 MUST 不顯示
- **FR-008**: Guest Mode 下，使用者透過 URL 直接造訪 `/settings` 時，MUST 顯示需要帳號的提示頁（含登入/註冊連結），而非顯示設定內容或空白頁
- **FR-009**: Guest Mode 下，`/graph` 頁面 MUST 僅呈現對應第一頁文章的知識圖譜資料
- **FR-010**: Guest 完成正式登入後，系統 MUST 清除 Guest Mode 狀態並賦予完整使用者權限

### Key Entities

- **Guest Mode 狀態**: 純前端管理的輕量 demo session，區別於「已登入」和「完全未登入」；無需後端帳號或 token，以瀏覽器 session 層級的機制儲存

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 使用者能在 2 個步驟以內（造訪登入頁 → 點擊一次）進入 Guest Mode 並看到真實文章
- **SC-002**: 完全未登入的一般訪客看到的 paywall 行為與現在完全相同（零行為迴歸）
- **SC-003**: Guest 無法透過任何 URL 存取 settings 頁面的功能內容（100% 封鎖）
- **SC-004**: Guest 看到的圖譜節點數量不超過一個 topic 第一頁的文章數量
- **SC-005**: Guest Mode 頁面重整後仍維持狀態（在同一 session 生命週期內）

## Assumptions

- 後端 articles 和 graph API 均為 Public（不需要 auth token），Guest 可直接呼叫，無需後端改動
- Guest Mode 狀態以瀏覽器 sessionStorage 實作（分頁關閉後自動清除，不持久化至 localStorage）
- Guest Mode 不走 NextAuth session；狀態完全由前端 Context 管理，無需 JWT 或 backend session
- FilterBar 對 Guest 顯示，但後端呼叫固定帶 `page=1`
- `/admin/*` 路由的保護維持現有機制（middleware 層），Guest 存取行為等同一般未登入訪客
- 登入頁的「以訪客身份繼續」選項視覺上低調於主要登入按鈕（tertiary / text link 層級），以保持登入為主要 CTA
