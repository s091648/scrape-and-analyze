# Design Validation Report: Digital Twins Scraper (Rev. 2)

**Reviewer Role:** AWS Cloud Architect & QA Lead  
**Target Document:** `changes/digital-twins-scraper/design.md` (Revision 2)  
**Date:** 2026-01-27

本報告針對修訂後的設計文件進行第二輪審查。
**總評：** 該版本已大幅改善了第一版提出的缺失。可觀測性 (Observability)、測試計畫 (Test Plan)、以及開發環境一致性 (Docker) 皆已完善。然而，在 **資料庫主鍵設計與去重機制** 的交互作用上發現了一個邏輯上的 **Gating Issue**，必須修正以確保系統能達成 "避免重複爬取" 的目標。

---

## 1. Gating Issues (Must Fix Before Implementation)

### [G1] DynamoDB Deduplication 機制與 PK 設計衝突
- **Principle Reference:** Point 8 (Capacity/Data Integrity)
- **Location:** `D3 (DynamoDB Table)` & `R4 (Risks - Data Duplication)`
- **Issue:**
    - `D3` 定義 `ArticlesTable` 的 Primary Key (PK) 為 `article_id` (UUID)。
    - `R4` 提到使用 "DynamoDB Conditional Write" 透過 URL 來避免重複。
    - **Technical Flaw:** DynamoDB 的 Condition Expression (`attribute_not_exists(url)`) **只能針對當下寫入的那筆 PK (Item) 進行檢查**。
    - 如果每次爬蟲都產生一個 **隨機 UUID** 作為 `article_id`，對 DynamoDB 來說這就是一筆全新的資料 (New Item)。在寫入這筆新 UUID 時，檢查它是否包含重複 URL 是沒有意義的（因為它是新的，當然沒有）。
    - 除非你先進行 `Scan`/`Query` (低效)，否則無法跨 Items 檢查 URL 是否存在。
- **Recommendation:**
    1. **方案 A (推薦)**: 將 PK (`article_id`) 改為 **URL 的確定性 Hash** (e.g., SHA-256 string of the URL) 或 **基於 URL 的 UUIDv5**。這樣相同的 URL 永遠會產生相同的 PK，Conditional Write (`attribute_not_exists(pk)`) 才能生效。
    2. **方案 B**: 直接使用 `url` 作為 PK (需注意長度限制與熱點問題，通常 Hash 較佳)。
    - **Action:** 請修改 `D3` 的 PK 定義與生成邏輯，確保 Idempotency。

---

## 2. Non-Gating Risks (Address Plan Required)

### [R1] HTML Sanitization 的實作細節與 LLM 理解力
- **Principle Reference:** Point 11 (Input Cleaning)
- **Location:** `D11 (輸入清洗)`
- **Issue:** 策略中提到 "HTML Tag Stripping: 移除所有 HTML 標籤"。
    - 若單純移除標籤 (e.g., `<h1>Title</h1><p>Body</p>` -> `TitleBody`)，會導致文字黏連，丟失段落結構，嚴重影響 LLM 的語意理解能力。
- **Recommendation:**
    - 應修正為 **"HTML to Text Conversion"**。
    - 使用如 `BeautifulSoup.get_text(separator='\n')` 的方式，將區塊元素 (Block elements) 轉換為換行符號，保留文章結構供 LLM 分析。

### [R2] 敏感資訊 (Secrets) 的傳遞方式
- **Principle Reference:** Point 5 (Security)
- **Location:** `D5 (LLM Provider)` & `D9 (IAM)`
- **Issue:** 設計提到透過環境變數傳遞 `api_key`，但未明確說明在 CDK 中如何處理。
- **Recommendation:**
    - 確保在 `ScraperStack` 中，API Key 是從 **AWS Secrets Manager** 或是 **SSM Parameter Store (SecureString)** 讀取。
    - 在 Lambda 環境變數中，建議透過 CDK 的 `SecretValue` 注入，或者在 Lambda 啟動時透過 SDK 動態讀取 (更安全，避免 Key 出現在 Lambda Console 的 Environment Variables 明文中)。

---

## 3. Nitpicks (Suggestions for Optimization)

### [N1] ECR 權限範圍
- **Location:** `D9 (GitHub Actions 權限)`
- **Comment:** `ecr:*` 權限過大。建議縮限為 `ecr:GetAuthorizationToken` 以及針對特定 Repository 的 `BatchCheckLayerAvailability`, `PutImage` 等權限。

### [N2] SQS 重複訊息處理 (Idempotency)
- **Location:** `D4 (SQS)`
- **Comment:** 使用 Standard Queue 代表可能有 "At-Least-Once" Delivery (極低機率重複)。若 `AnalysisTable` 的 PK 是隨機生成的 UUID，重複的 SQS 訊息會導致重複扣款 (LLM Cost) 並產生兩筆分析結果。
- **Suggestion:** 若修正了 [G1]，讓 Article ID 為確定性 Hash，並將其傳遞給 SQS，則 Analyzer 可利用 Article ID 作為 Idempotency Key，避免重複執行。

---

**Summary:**
設計成熟度已達 90%。請務必修正 **[G1] DynamoDB PK 設計** 以確保去重機制能真實運作，其餘項目為實作細節提醒。修正後即可進入開發階段。
