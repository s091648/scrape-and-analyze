# Feature Specification: Semantic Scholar + OpenAlex Scraper

**Feature Branch**: `feat/semantic_scholar`

**Created**: 2026-06-04

**Updated**: 2026-06-05 (rev 2 — 新增 US5/US6、FR-018~FR-023、bug fix 記錄)

**Status**: In Progress

**Input**: User description: "新增 Semantic Scholar scraper 至 scraping pipeline，以解決 arXiv rate limit 問題，同時擴大論文來源涵蓋範圍。實作後發現 Semantic Scholar 免費 API 無法個人申請 key，且首次執行即 429；改以 OpenAlex 作為主要免費學術論文 API 並同步實作。"

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

### User Story 4 - 以 OpenAlex 抓取學術論文（Priority: P1）

身為管理員，我希望能在 Scraper Settings 頁面為某個 topic 啟用 OpenAlex 來源，設定關鍵字與抓取頻率，讓系統自動定期從 OpenAlex 搜尋並收集相關論文。

**Why this priority**: Semantic Scholar 免費 API 無法個人申請 key（需機構帳號），且首次請求即觸發 429（IP 層級封鎖）。OpenAlex 為完全免費的學術論文索引 API，無需任何 API key，透過 polite pool（User-Agent 帶 mailto）可穩定取得 10 req/sec。資料來源同等豐富（含 ArXiv、DOI、開放取用 PDF URL、引用數、摘要）。

**Independent Test**: 在 admin UI 啟用 OpenAlex + 加入 keyword，手動觸發 `make scrape SOURCE=openalex LIMIT=3`，確認資料庫出現 `source = 'openalex'` 的論文並顯示於前端。

**Acceptance Scenarios**:

1. **Given** 管理員已登入且選取一個 topic，**When** 在 Scraper Settings 點擊「啟用 OpenAlex」並設定 keyword 與頻率後儲存，**Then** 系統應新增一筆 OpenAlex 設定，並在下次排程週期自動執行搜尋。
2. **Given** OpenAlex 設定已啟用且有有效 keyword，**When** scraper 執行 discover，**Then** 應回傳符合 keyword 的論文清單（含標題、摘要、作者、發表日期）。
3. **Given** 系統抓到一篇 OpenAlex 論文且其有 ArXiv ID，**When** 比對已存在資料庫的論文，**Then** 系統應使用 ArXiv URL 去重，跳過重複論文。
4. **Given** OpenAlex abstract 以 inverted index 格式回傳，**When** client 解析論文，**Then** 應正確還原為可讀純文字。

---

---

### User Story 5 - 文章來源標示（原始出處 + 聚合器標籤）(Priority: P2)

身為讀者，當我瀏覽文章卡片時，我希望看到文章的真實原始出處（如 "arxiv"、"Nature"、"IEEE Transactions on..."），而非聚合器本身的名稱（"openalex" 或 "semantic_scholar"），並在旁邊附上小標籤說明「via OpenAlex」，讓我清楚知道論文的出處與抓取管道。

**Why this priority**: DOI URL 顯示為 "doi" 毫無意義。讀者需要知道論文來自哪個期刊或 preprint 伺服器，而不只是聚合器。

**Independent Test**: 觀察 OpenAlex 抓到的 arXiv 論文，卡片應顯示 "arxiv" badge 加上 "via OpenAlex" 小標；期刊論文應顯示期刊名稱（如 "Nature Neuroscience"）加上 "via OpenAlex"。

**Acceptance Scenarios**:

1. **Given** 一篇透過 OpenAlex 抓取且有 ArXiv ID 的論文，**When** 顯示文章卡片，**Then** source badge 應顯示 "arxiv"，並加上 "via OpenAlex" 小標籤。
2. **Given** 一篇透過 OpenAlex 抓取且無 ArXiv ID（只有 DOI）的論文，**When** 顯示文章卡片，**Then** source badge 應顯示期刊名稱（從 `primary_location.source.display_name` 取得），並加上 "via OpenAlex" 小標籤。
3. **Given** 一篇透過 Semantic Scholar 抓取且有 ArXiv ID 的論文，**When** 顯示文章卡片，**Then** source badge 應顯示 "arxiv"，並加上 "via Semantic Scholar" 小標籤。
4. **Given** 非聚合器來源的論文（`source = "arxiv"` 直接抓取），**When** 顯示文章卡片，**Then** source badge 正常顯示 "arxiv"，不顯示 "via" 標籤。

---

### User Story 6 - 文章列表聚合器篩選（Priority: P2）

身為讀者，我希望在文章列表頁能透過聚合器（OpenAlex / Semantic Scholar）來篩選文章，讓我專門檢視某一聚合器抓到的論文。這與現有 Source 篩選是獨立的維度。

**Why this priority**: 讀者可能想評估 OpenAlex vs Semantic Scholar 的論文品質，或追蹤特定聚合器的覆蓋範圍。

**Independent Test**: 在 Filter Bar 點選「Aggregator: OpenAlex」，確認列表只顯示 `source = 'openalex'` 的文章。URL 中出現 `aggregator=openalex` query param。

**Acceptance Scenarios**:

1. **Given** 文章列表頁已有 Filter Bar，**When** 展開 filter panel，**Then** 應看到「Aggregator」選項，固定提供 "openalex" 與 "semantic_scholar" 兩個選項。
2. **Given** 選擇了 Aggregator: OpenAlex，**When** 套用篩選，**Then** URL 加入 `aggregator=openalex`，文章列表只顯示 `source = 'openalex'` 的文章。
3. **Given** 同時選擇了 Aggregator 和 Source 篩選，**When** 套用，**Then** 兩者 AND 組合，只顯示同時符合的文章。
4. **Given** Knowledge Graph 頁面，**When** 展開 Filter Bar，**Then** Aggregator 篩選同樣出現並正常運作。

---

### Edge Cases

**Semantic Scholar**:
- 若 Semantic Scholar API 回傳的論文同時有 ArXiv ID，系統應使用 ArXiv URL（`https://arxiv.org/abs/{id}`）作為去重依據。
- 若 Semantic Scholar API 回傳 HTTP 429，系統應記錄警告並跳過本次執行，不應中斷整條 pipeline。
- 若 keyword 搜尋無結果，系統應正常結束本次 discover，記錄 info log，不視為錯誤。
- 若 PDF 下載失敗或解析失敗，系統應退回使用摘要，不應因此丟棄該論文。
- 若未設定 Semantic Scholar API key，系統應以免費層運作（受限於 IP 配額），不阻斷功能。

**OpenAlex**:
- OpenAlex 的 abstract 以 inverted index 格式（word → position list）儲存，client 必須在解析時還原為純文字。
- 若論文有 ArXiv ID（`ids.arxiv`），系統應使用 ArXiv URL 作為正規化 URL；若有 DOI 則使用 DOI URL；否則使用 OpenAlex URL（`https://openalex.org/W...`）。
- 若 OpenAlex API 回傳 HTTP 429，系統應記錄警告並跳過本次執行，不應中斷 pipeline。
- polite pool 需在 User-Agent 帶上 `mailto:` 電子信箱（從環境變數 `OPENALEX_MAILTO` 讀取）；未設定時仍可運作但速率較低。
- OpenAlex 預設 `Accept-Encoding` 不可包含 `br`（Brotli），因 `requests` 套件未安裝 `brotli` 時無法解碼，會導致 JSON 解析失敗。
- OpenAlex 搜尋結果 MUST 套用基礎過濾器（`type:article,has_abstract:true,is_retracted:false`）以排除非期刊文章；排序應使用 `relevance_score:desc` 而非純日期排序，避免回傳與查詢無關的近期論文。

**Article Source Display**:
- 前端文章卡片 MUST 顯示「真實原始出處」（`original_source`），而非聚合器的 `source` 欄位名稱。
- `original_source` 於 scraping 時由後端解析並存入 `metadata_` JSONB；前端直接讀取，不靠 URL heuristics。
- 若 `original_source` 不存在（舊資料），前端應 fallback 至 URL hostname 解析（arxiv.org → "arxiv" 等）。
- `via_source` 欄位儲存聚合器名稱（"openalex" / "semantic_scholar"）；非聚合器來源的文章 `via_source` 為 null，不顯示標籤。

## Requirements *(mandatory)*

### Functional Requirements

**Semantic Scholar**:
- **FR-001**: 系統 MUST 支援 `semantic_scholar` 作為一個獨立的 scraper 來源類型，可在 Scraper Settings 中針對每個 topic 進行設定。
- **FR-002**: Semantic Scholar 設定 MUST 以 singleton 模式運作（每個 topic 最多一個），介面設計與 ArXiv 設定卡片平行對稱。
- **FR-003**: 管理員 MUST 能在 Semantic Scholar 設定中管理 topic 層級的關鍵字清單（新增、刪除），這些關鍵字用於 Semantic Scholar API 搜尋。
- **FR-004**: 系統 MUST 支援為 Semantic Scholar 設定 `max_results`（每次最多回傳幾篇）與 `days_back`（只搜尋最近 N 天的論文）兩個參數。
- **FR-005**: 系統 MUST 在有開放取用 PDF 時自動下載並解析全文，無 PDF 時退回摘要，兩種情況都不中斷流程。
- **FR-006**: 系統 MUST 對 Semantic Scholar 回傳的論文進行 URL 去重：若論文有 ArXiv ID 則使用 ArXiv URL 作為正規化 URL，否則使用 Semantic Scholar 論文頁 URL。
- **FR-007**: 系統 MUST 支援透過環境變數 `SEMANTIC_SCHOLAR_API_KEY` 設定 API key；未設定時應退回免費層運作（受 IP 配額限制）。
- **FR-008**: LLM 分析流程 MUST 對 `semantic_scholar` 來源的論文採用與 ArXiv 相同的內容擷取邏輯（有段落則用全文截斷為上限，無段落則用摘要）。
- **FR-009**: ArXiv scraper MUST 在系統層面忽略 `arxiv_keyword` 類型的設定，只使用 `arxiv_category` 類型的設定進行查詢。
- **FR-010**: ArXiv Scraper Settings 介面 MUST 移除 keyword 管理區塊，只保留 category 管理區塊；現有 category 功能不受影響。

**OpenAlex**:
- **FR-011**: 系統 MUST 支援 `openalex` 作為一個獨立的 scraper 來源類型，可在 Scraper Settings 中針對每個 topic 進行設定。
- **FR-012**: OpenAlex 設定 MUST 以 singleton 模式運作（每個 topic 最多一個），介面設計與 Semantic Scholar 設定卡片平行對稱。
- **FR-013**: 管理員 MUST 能在 OpenAlex 設定中管理 topic 層級的關鍵字清單（`openalex_keyword` 類型，新增、刪除）。
- **FR-014**: 系統 MUST 支援為 OpenAlex 設定 `max_results` 與 `days_back` 兩個參數；`max_results` 上限為 200（OpenAlex API 單次最大值）。
- **FR-015**: OpenAlexClient MUST 還原 abstract inverted index 格式為純文字後儲存，並從 `ids.arxiv` / `doi` 正規化 URL；有開放取用 PDF 時同樣走 PdfParser 解析全文。搜尋時 MUST 套用基礎過濾器（`type:article,has_abstract:true,is_retracted:false`）並以 `relevance_score:desc` 排序。
- **FR-016**: 系統 MUST 透過環境變數 `OPENALEX_MAILTO` 讓 OpenAlex client 在 User-Agent 帶 mailto，以進入 polite pool（10 req/sec）；未設定時仍可運作但速率受預設限制。HTTP client `Accept-Encoding` MUST NOT 包含 `br`（Brotli）。
- **FR-017**: LLM 分析流程 MUST 對 `openalex` 來源的論文採用與 ArXiv、Semantic Scholar 相同的內容擷取邏輯。

**Article Source Attribution** (US5):
- **FR-018**: 聚合器 scraper（SS / OA）在 discover/fetch 時 MUST 將 `via_source`（聚合器名稱）與 `original_source`（原始出處，如 "arxiv" 或期刊名稱）存入 Article `metadata_` JSONB 欄位；無需 DB schema 變更。
- **FR-019**: `original_source` 解析規則：若論文有 ArXiv ID → "arxiv"；否則取 OpenAlex `primary_location.source.display_name`（期刊名稱）或 Semantic Scholar 直接為 "semanticscholar"。
- **FR-020**: 後端 `ArticleOut` / `ArticleDetailOut` MUST 暴露 `via_source: Optional[str]` 與 `original_source: Optional[str]` 欄位（從 `metadata_` 讀取）。
- **FR-021**: 前端文章卡片與文章詳情 dialog MUST 顯示 `original_source`（而非 scraper `source` 欄位）作為主要來源 badge；若 `via_source` 存在則額外顯示 "via OpenAlex" / "via Semantic Scholar" 小標籤。

**Aggregator Filter** (US6):
- **FR-022**: 後端 `/articles` API MUST 支援 `aggregator: List[str]` query 參數，過濾 `Article.source IN (aggregator)` 的文章；與現有 `source` 篩選獨立，可同時使用。
- **FR-023**: 前端文章列表 Filter Bar MUST 新增 Aggregator 篩選（固定選項：openalex、semantic_scholar），透過 `aggregator` URL query param 傳遞；Knowledge Graph 頁面的 Filter Bar 同步支援。

**Admin UI** (US1/US4 更新):
- **FR-024**: Scraper Settings 頁面 MUST 將 Semantic Scholar 與 OpenAlex 兩個設定卡片整合於同一「Aggregator」accordion section 下，新增聚合器時以 dialog 選擇類型（SS / OA）後再展開對應設定卡片。

### Key Entities

- **SemanticScholarSetting**：Semantic Scholar 的抓取設定，包含啟用狀態、頻率、max_results、days_back，隸屬於某個 topic。每個 topic 最多一筆（singleton）。
- **SemanticScholarKeyword**：用於 Semantic Scholar API 搜尋的關鍵字，屬於 topic 層級，一個 topic 可有多個 keyword。
- **SemanticScholarPaper**：從 Semantic Scholar API 取得的論文資料，包含 paper ID、標題、摘要、作者、發表日期、開放取用 PDF URL、DOI、ArXiv ID、引用數。此為中間資料，最終儲存為系統統一的 Article 格式。
- **OpenAlexSetting**：OpenAlex 的抓取設定，與 SemanticScholarSetting 結構相同，每個 topic 最多一筆（singleton）。
- **OpenAlexKeyword**：用於 OpenAlex search API 的關鍵字，`keyword_type = "openalex_keyword"`，屬於 topic 層級。
- **OpenAlexWork**：從 OpenAlex API 取得的論文資料，包含 work ID、標題（需從 abstract inverted index 還原摘要）、作者、發表日期、開放取用 PDF URL、DOI、ArXiv ID、引用數。此為中間資料，最終儲存為系統統一的 Article 格式。
- **ArticleSourceMetadata**：儲存於 `Article.metadata_` JSONB 中的來源相關欄位：`via_source`（聚合器名稱，如 "openalex"）、`original_source`（原始出處，如 "arxiv"、"Nature Neuroscience"）、`primary_topic`（OpenAlex primary topic 名稱）、`primary_field`（OpenAlex field 名稱）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 管理員可在 3 分鐘內完成啟用 Semantic Scholar 或 OpenAlex 來源、設定關鍵字、儲存設定的完整流程。
- **SC-002**: 單次 Semantic Scholar scrape 執行（20 篇論文）應在 60 秒內完成（不含 PDF 下載）。
- **SC-003**: 在多來源（SS / OpenAlex / ArXiv）同時啟用的情況下，系統應確保同一篇論文不重複出現在論文列表中（去重率 100%）。
- **SC-004**: ArXiv scraper 在移除 keyword 搜尋後，rate limit 錯誤（HTTP 429）應降低至每週 0 次（category-only 查詢量遠低於 rate limit 閾值）。
- **SC-005**: 有開放取用 PDF 的論文，其 LLM 分析結果的標籤豐富度（tag 數量）應高於純摘要分析的同類論文。
- **SC-006**: OpenAlex scrape 在無 API key 情況下（僅 mailto polite pool）應能穩定執行，不出現 HTTP 429（rate limiter 設定 5 RPM，遠低於 polite pool 10 req/sec 上限）。
- **SC-007**: 透過聚合器抓取的 arXiv 論文，文章卡片 source badge 應正確顯示 "arxiv"（而非 "doi" 或聚合器名稱），正確率 100%。
- **SC-008**: OpenAlex 回傳結果應為期刊文章（非書籍章節、資料集等），且有摘要，且未撤稿；`_BASE_FILTERS` 確保過濾品質。

## Assumptions

- 系統已有 ArXiv scraper 運作，本功能為並行新增，不取代 ArXiv。
- **Semantic Scholar**：免費 API 無法個人申請 key（需機構帳號），且未驗證 IP 的速率限制極為嚴格（首次執行即 HTTP 429）。保留 Semantic Scholar 實作，但以 OpenAlex 作為主要免費學術論文來源。若未來取得 API key，SS 實作可直接啟用。
- **OpenAlex**：完全免費，無需 API key；透過 mailto polite pool 可穩定取得 10 req/sec，rate limiter 設定 5 RPM 確保安全邊際。abstract 以 inverted index 格式儲存，client 層負責還原。
- 現有資料庫中已存在的 `arxiv_keyword` 資料不需清除，系統層忽略即可（無需資料遷移）。
- 前端 Scraper Settings 頁面採用 AccordionSection 區塊佈局；Semantic Scholar 與 OpenAlex 合併為單一「Aggregator」accordion，新增時透過 dialog 選擇類型。
- 論文 PDF 解析邏輯（PdfParser）現有實作可直接複用，無需修改。
- 去重機制（UrlHash）現有實作可直接複用；URL 正規化邏輯在各 scraper client 內處理（ArXiv URL 優先 → DOI URL → 來源 URL）。
- 本功能不包含論文引用關係（citation graph）的收集或展示。
- 本功能只使用 keyword search API，不使用個人化推薦 API。
