# Feature Specification: Article Sharing via URL

**Feature Branch**: `feat/article_id_and_guest`

**Created**: 2026-05-30

**Status**: Draft

**Input**: User description: "把 article-id 放入 query parameter，讓 URL 可以直接導向特定文章；在 ArticleCard 上新增 share icon；share 出來的 link 導向一個獨立的 layout，只顯示被選定的 ArticleCard。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 開啟文章時 URL 同步更新 (Priority: P1)

使用者在主頁點開某篇文章的詳細對話框後，瀏覽器的 URL query params 自動更新，包含當前的 `topic_id` 與 `article_id`。關閉對話框後，query params 清除。

**Why this priority**: URL 同步是分享功能的基礎；沒有這個，分享連結無法正確還原文章。

**Independent Test**: 開啟文章 → 檢查 URL 有 `?article=<id>` → 關閉 → URL 恢復，可獨立驗證。

**Acceptance Scenarios**:

1. **Given** 使用者在主頁（已選定 topic），**When** 點擊任一 ArticleCard 開啟對話框，**Then** URL 更新為 `/?topic=<topicId>&article=<articleId>`
2. **Given** 文章對話框已開啟，**When** 使用者關閉對話框，**Then** URL 中的 `article` query param 被移除
3. **Given** 使用者持有含 `article` param 的 URL，**When** 直接打開該 URL，**Then** 主頁自動開啟對應文章的詳細對話框

---

### User Story 2 - 複製分享連結 (Priority: P2)

使用者在 ArticleCard 上點擊 share 圖示，系統將包含 `topic_id` 和 `article_id` 的完整 URL 複製到剪貼簿，並提供視覺回饋。

**Why this priority**: 這是「分享」的核心 UX 動作，讓使用者可以傳送連結給他人。

**Independent Test**: 點擊 share icon → 剪貼簿取得正確 URL → toast 確認訊息顯示，可獨立驗證。

**Acceptance Scenarios**:

1. **Given** ArticleCard 顯示於列表中，**When** 使用者懸停 (hover) 在卡片上，**Then** share icon 顯示（與現有 ExternalLink icon 行為一致）
2. **Given** share icon 可見，**When** 使用者點擊 share icon，**Then** 包含完整參數的 URL 被複製到剪貼簿
3. **Given** 複製成功，**When** 複製動作完成，**Then** 顯示短暫的成功回饋（如 toast 或 icon 狀態變化）
4. **Given** 使用者點擊 share icon，**When** 瀏覽器不支援 Clipboard API，**Then** 顯示錯誤提示，不靜默失敗

---

### User Story 3 - 獨立文章分享頁面 (Priority: P3)

收到分享連結的使用者打開一個獨立的頁面，頁面只顯示目標文章的 ArticleCard，沒有 NavBar、FilterBar、pagination 或其他功能。

**Why this priority**: 讓非使用者（如分享對象）可以乾淨地預覽文章，不受主頁其他元素干擾。

**Independent Test**: 造訪 `/articles/<id>` → 僅顯示文章卡片，無其他 UI 元素，可獨立驗證。

**Acceptance Scenarios**:

1. **Given** 使用者造訪 `/articles/<articleId>`，**When** 頁面載入，**Then** 只顯示對應文章的 ArticleCard（含標題、內容摘要、來源、日期）
2. **Given** 獨立分享頁，**When** 頁面顯示，**Then** 沒有 NavBar、FilterBar、分頁元件或任何其他主頁 UI
3. **Given** 文章 ID 不存在，**When** 造訪對應 URL，**Then** 顯示適當的 404 或錯誤訊息
4. **Given** 使用者在分享頁查看文章，**When** 點擊 ExternalLink icon，**Then** 在新頁籤開啟原文連結

---

### Edge Cases

- 當 `article_id` 存在於 URL 但 `topic_id` 不存在或不匹配時，系統應能獨立以 article_id 查詢文章
- 使用者分享連結後，若文章被刪除，分享頁應顯示適當的錯誤訊息
- 同一頁面快速切換不同文章時，URL 應正確更新而不產生歷史記錄堆疊問題（replace 而非 push）

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 使用者開啟文章對話框時，系統 MUST 將 `article_id`（及當前 `topic_id`）更新至 URL query params，使用 replace 模式（不新增瀏覽器歷史記錄）
- **FR-002**: 使用者關閉文章對話框時，系統 MUST 移除 URL 中的 `article` query param
- **FR-003**: 頁面載入時若 URL 含有 `article` query param，系統 MUST 自動開啟對應文章的對話框
- **FR-004**: ArticleCard MUST 提供 share icon，點擊後將 `/articles/<articleId>?topic=<topicId>` 格式的 URL 複製到剪貼簿（不再使用 `/?topic=...&article=...` 格式）
- **FR-005**: 複製到剪貼簿後，系統 MUST 顯示成功回饋：share icon 切換為 Check icon（持續約 2 秒），並顯示 toast 通知（待 sonner 安裝後補上）
- **FR-006**: Clipboard API 不可用時，系統 MUST 顯示 toast 錯誤訊息（待 sonner 安裝後補上，目前靜默處理）
- **FR-007**: 系統 MUST 提供路由 `/articles/[articleId]` 作為獨立分享頁，使用與主頁 root layout 完全分離的 layout（無 NavBar 等共用元件）；右上角根據登入狀態顯示情境提示：已登入或 guest 顯示「在 App 中開啟」連結，未登入顯示「登入查看更多文章」連結
- **FR-008**: 獨立分享頁 MUST 顯示完整的 ArticleCard 內容（標題、來源、日期、內容摘要、外部連結）
- **FR-009**: 獨立分享頁的 article_id 不存在時，MUST 顯示 404 或明確錯誤狀態

### Key Entities

- **Article**: 文章主體，包含 id、title、source、content、published_at、url；id 為分享連結的核心識別碼
- **Share URL**: 由 `topic_id` + `article_id` 組成的可分享連結；獨立分享頁僅需 `article_id`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 使用者能在 3 個步驟以內（hover → click share → paste）完成文章分享
- **SC-002**: 分享連結在新的瀏覽器視窗中打開時，能正確顯示對應文章（成功率 100%，排除文章已刪除的情況）
- **SC-003**: URL 同步在使用者開啟/關閉對話框的 200ms 以內完成更新
- **SC-004**: 獨立分享頁僅顯示目標文章，頁面中不存在任何主頁導覽元件

## Assumptions

- 分享連結的接收者可能是未登入的訪客，獨立分享頁面不要求登入即可瀏覽（公開存取）
- 獨立分享頁使用 article_id 直接向後端查詢文章，不依賴 topic_id 篩選
- URL query param 名稱使用 `article`（例：`?topic=abc&article=xyz`）
- Share icon 的視覺風格與現有 ExternalLink icon 保持一致（hover 才顯示）
- 同一個 ArticleCard 元件在主頁和獨立分享頁都能使用，不需要建立新的卡片元件
- 獨立分享頁不包含 i18n 切換或主題切換功能（保持最簡）
