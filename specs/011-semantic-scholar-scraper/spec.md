# Feature Specification: Semantic Scholar Scraper

**Feature Branch**: `feat/semantic_scholar`

**Created**: 2026-06-04

**Status**: Draft

**Input**: User description: "新增 Semantic Scholar scraper 至 scraping pipeline，以解決 arXiv rate limit 問題，同時擴大論文來源涵蓋範圍。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 設定 Semantic Scholar 來源並自動抓取論文 (Priority: P1)

身為管理員，我希望能在 Scraper Settings 頁面為某個 topic 啟用 Semantic Scholar 來源，設定關鍵字與抓取頻率，讓系統自動定期從 Semantic Scholar 搜尋並收集相關論文。

**Why this priority**: 這是核心功能。若無此功能，其餘設計均無意義。Semantic Scholar 的搜尋 API 覆蓋 ArXiv、ACM、IEEE 等多個來源，能大幅減少因 ArXiv rate limit 造成的抓取失敗。

**Independent Test**: 可在管理頁面新增一個 Semantic Scholar 設定卡片並加入 keyword，手動觸發 scrape 後確認資料庫中出現新論文，並確認這些論文顯示在前端論文列表中。

**Acceptance Scenarios**:

1. **Given** 管理員已登入且選取一個 topic，**When** 在 Scraper Settings 點擊「啟用 Semantic Scholar」並設定 keyword 與頻率後儲存，**Then** 系統應新增一筆 Semantic Scholar 設定，並在下次排程週期自動執行搜尋。
2. **Given** Semantic Scholar 設定已啟用且有有效 keyword，**When** scraper 執行 discover，**Then** 應回傳符合 keyword 的論文清單（含標題、摘要、作者、發表日期）。
3. **Given** 系統抓到一篇 Semantic Scholar 論文，**When** 該論文已存在於資料庫（無論是從 ArXiv 還是 Semantic Scholar 抓取），**Then** 系統應跳過該論文不重複儲存。

---

### User Story 2 - 開放取用論文取得全文供 LLM 分析 (Priority: P2)

身為管理員，我希望系統對有開放取用 PDF 的論文能自動下載並解析全文段落，以提供 LLM 更豐富的分析素材，而不僅限於摘要。

**Why this priority**: 全文分析的品質顯著優於純摘要分析，尤其對研究方法、實驗結果等段落的標籤提取。

**Independent Test**: 抓取一篇已知有開放取用 PDF 的論文（例如 ArXiv 上的論文透過 Semantic Scholar 取得），確認其 LLM 分析結果中包含 `Introduction`、`Methods` 等段落資訊，而非僅有摘要。

**Acceptance Scenarios**:

1. **Given** Semantic Scholar 回傳的論文有開放取用 PDF 連結，**When** scraper 執行 fetch，**Then** 系統應下載 PDF 並解析出各章節文字，存入論文 metadata。
2. **Given** 論文沒有開放取用 PDF（僅限訂閱），**When** scraper 執行 fetch，**Then** 系統應退回使用摘要作為分析內容，不應因缺少 PDF 而中斷流程。
3. **Given** 有 PDF 且解析出多個章節，**When** LLM 進行分析，**Then** 應使用完整章節文字（上限 15,000 字）作為分析輸入。

---

### User Story 3 - ArXiv 設定精簡為只使用分類訂閱 (Priority: P3)

身為管理員，我希望 ArXiv 的設定介面只允許設定分類（category）而非關鍵字搜尋，因為 ArXiv 關鍵字搜尋是導致 rate limit 的主因，且這項功能已由 Semantic Scholar 承接。

**Why this priority**: 此變更是 rate limit 解決方案的配套措施。Semantic Scholar 負責關鍵字搜尋，ArXiv 只負責分類訂閱，兩者各司其職。

**Independent Test**: 在 ArXiv 設定介面確認「新增 keyword」的輸入區塊已消失，只剩「新增 category」的區塊，且現有 ArXiv category 設定仍正常運作。

**Acceptance Scenarios**:

1. **Given** 管理員開啟 ArXiv 設定頁面，**When** 查看 ArXiv 卡片，**Then** 應只看到 category 管理區塊，keyword 管理區塊已移除。
2. **Given** 資料庫中有舊的 `arxiv_keyword` 資料，**When** ArXiv scraper 執行，**Then** 舊的 keyword 應被忽略不使用（不產生查詢），只使用 category。
3. **Given** ArXiv 只設定了 categories（無 keywords），**When** scraper 執行，**Then** 應正常依 category 抓取論文，不受影響。

---

### Edge Cases

- 若 Semantic Scholar API 回傳的論文同時有 ArXiv ID，系統應使用 ArXiv URL（`https://arxiv.org/abs/{id}`）作為去重依據，避免與 ArXiv scraper 重複收錄同一篇論文。
- 若 Semantic Scholar API 回傳 HTTP 429（rate limit），系統應記錄警告並跳過本次執行，不應中斷整條 pipeline。
- 若 keyword 搜尋無結果（零篇論文），系統應正常結束本次 discover，記錄 info log，不視為錯誤。
- 若 PDF 下載失敗或解析失敗，系統應退回使用摘要，不應因此丟棄該論文。
- 若未設定 Semantic Scholar API key，系統應以免費層（每秒 1 請求）運作，不阻斷功能。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系統 MUST 支援 `semantic_scholar` 作為一個獨立的 scraper 來源類型，可在 Scraper Settings 中針對每個 topic 進行設定。
- **FR-002**: Semantic Scholar 設定 MUST 以 singleton 模式運作（每個 topic 最多一個），介面設計與 ArXiv 設定卡片平行對稱。
- **FR-003**: 管理員 MUST 能在 Semantic Scholar 設定中管理 topic 層級的關鍵字清單（新增、刪除），這些關鍵字用於 Semantic Scholar API 搜尋。
- **FR-004**: 系統 MUST 支援為 Semantic Scholar 設定 `max_results`（每次最多回傳幾篇）與 `days_back`（只搜尋最近 N 天的論文）兩個參數。
- **FR-005**: 系統 MUST 在有開放取用 PDF 時自動下載並解析全文，無 PDF 時退回摘要，兩種情況都不中斷流程。
- **FR-006**: 系統 MUST 對 Semantic Scholar 回傳的論文進行 URL 去重：若論文有 ArXiv ID 則使用 ArXiv URL 作為正規化 URL，否則使用 Semantic Scholar 論文頁 URL。
- **FR-007**: 系統 MUST 支援透過環境變數設定 Semantic Scholar API key；未設定時應退回免費層運作。
- **FR-008**: LLM 分析流程 MUST 對 `semantic_scholar` 來源的論文採用與 ArXiv 相同的內容擷取邏輯（有段落則用全文截斷為上限，無段落則用摘要）。
- **FR-009**: ArXiv scraper MUST 在系統層面忽略 `arxiv_keyword` 類型的設定，只使用 `arxiv_category` 類型的設定進行查詢。
- **FR-010**: ArXiv Scraper Settings 介面 MUST 移除 keyword 管理區塊，只保留 category 管理區塊；現有 category 功能不受影響。

### Key Entities

- **SemanticScholarSetting**：Semantic Scholar 的抓取設定，包含啟用狀態、頻率、max_results、days_back，隸屬於某個 topic。每個 topic 最多一筆（singleton）。
- **SemanticScholarKeyword**：用於 Semantic Scholar API 搜尋的關鍵字，屬於 topic 層級，一個 topic 可有多個 keyword。
- **SemanticScholarPaper**：從 Semantic Scholar API 取得的論文資料，包含 paper ID、標題、摘要、作者、發表日期、開放取用 PDF URL、DOI、ArXiv ID、引用數。此為中間資料，最終儲存為系統統一的 Article 格式。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 管理員可在 3 分鐘內完成啟用 Semantic Scholar 來源、設定關鍵字、儲存設定的完整流程。
- **SC-002**: 單次 Semantic Scholar scrape 執行（20 篇論文）應在 60 秒內完成（不含 PDF 下載）。
- **SC-003**: 在 Semantic Scholar 與 ArXiv 同時啟用的情況下，系統應確保同一篇論文不重複出現在論文列表中（去重率 100%）。
- **SC-004**: ArXiv scraper 在移除 keyword 搜尋後，rate limit 錯誤（HTTP 429）應降低至每週 0 次（category-only 查詢量遠低於 rate limit 閾值）。
- **SC-005**: 有開放取用 PDF 的論文，其 LLM 分析結果的標籤豐富度（tag 數量）應高於純摘要分析的同類論文。

## Assumptions

- 系統已有 ArXiv scraper 運作，本功能為並行新增，不取代 ArXiv。
- Semantic Scholar API 免費層（無 API key）的 rate limit（1 req/sec）足以應付正常抓取頻率；如需更高頻率，使用者自行申請 API key。
- 現有資料庫中已存在的 `arxiv_keyword` 資料不需清除，系統層忽略即可（無需資料遷移）。
- 前端 Scraper Settings 頁面目前採用 AccordionSection 區塊佈局，新增 Semantic Scholar 區塊沿用此架構。
- 論文 PDF 解析邏輯（PdfParser）現有實作可直接複用，無需修改。
- 去重機制（UrlHash）現有實作可直接複用；URL 正規化邏輯在 Semantic Scholar scraper 內處理。
- 本功能不包含 Semantic Scholar 論文引用關係（citation graph）的收集或展示。
- 本功能不包含 Semantic Scholar 的 Recommendations API（個人化推薦），只使用 keyword search API。
