# Design Validation Report: Digital Twins Scraper

**Reviewer Role:** AWS Cloud Architect & QA Lead  
**Target Document:** `changes/digital-twins-scraper/design.md`  
**Date:** 2026-01-27

本報告基於 `@scrape-analyzer/qa_principle.md` 中的八大面向進行審查。以下列出需在開發前解決的 Gating Issues (阻擋性問題)、需關注的 Non-Gating Risks (非阻擋性風險) 以及建議改進的 Nitpicks (細節優化)。

---

## 1. Gating Issues (Must Fix Before Implementation)

### [G3] 測試驗收標準與覆蓋率定義缺失
- **Principle Reference:** Point 3 (Unit/Integration Test Criteria)
- **Issue:** 文件雖提及 TDD 與 CI/CD，但**完全缺乏具體的驗收標準 (Acceptance Criteria)**。
    - **Missing:** 針對爬蟲 Lambda，未定義如何測試 "部分失敗" (Partial Failure) 的場景（例如：RSS 格式錯誤但 API 正常）。
    - **Missing:** 針對解析 Lambda，未定義 LLM 輸出的驗證邏輯（例如：是否驗證 JSON Schema? 輸出為空或幻覺時的 Assert 條件為何?）。
    - **Missing:** 未定義整合測試 (Integration Test) 的範圍。是否包含 LocalStack 模擬 DynamoDB/SQS？或是針對真實 AWS 環境的 E2E 測試？
- **Action Required:** 需在設計文件中補上 `Test Plan` 章節，列出 Critical Path 的測試案例與預期的 Code Coverage 目標 (建議核心邏輯 > 80%)。

### [G4] 非同步架構的可觀測性 (Observability) 不足
- **Principle Reference:** Point 4 (System Observability)
- **Issue:** 系統採用 Event-Driven 架構 (Lambda -> SQS -> Lambda)，但設計中**未提及如何追蹤單一文章的完整生命週期**。
    - 若解析 Lambda 報錯，維運人員難以直接關聯到是哪一次的爬蟲任務產生的資料。僅靠 "Log errors" 在 CloudWatch Logs 中是大海撈針。
- **Action Required:** 
    - 必須引入 **AWS X-Ray** 或實作 **Structured Logging with Correlation IDs**。
    - 需定義 Log Group 的 retention policy 與 Log Structure（例如 JSON 格式），以便 CloudWatch Insights 查詢。

---

## 2. Non-Gating Risks (Address Plan Required)

### [R6] Cold Start 緩解策略過度設計 (Cost/Overkill)
- **Principle Reference:** Point 6 (Cost) & Point 8 (Capacity)
- **Issue:** 風險評估 `R2` 建議使用 **Provisioned Concurrency** 來解決 Cold Start。
    - **Analysis:** 對於一個 "每日/每週" 執行的 **Background Batch Job** 來說，Lambda Cold Start (通常 < 5-10秒) 對系統功能與使用者體驗**毫無影響**。啟用 Provisioned Concurrency 會導致 24/7 的額外費用，屬於 **Overkill**。
- **Recommendation:** 移除 Provisioned Concurrency 的建議，僅需調整 Lambda Timeout (例如設定為 5-10 分鐘) 即可。

### [R1] 錯誤處理缺乏 "DLQ Redrive" 流程
- **Principle Reference:** Point 1 (Error Handling)
- **Issue:** `D4` 與 `D7` 定義了 Dead Letter Queue (DLQ)，但**未定義當訊息進入 DLQ 後該如何處理**。
    - 訊息堆積在 DLQ 14天後會消失。如果沒有自動化告警 (CloudWatch Alarm on DLQ Depth) 或重驅動 (Redrive Policy) 機制，這些失敗的任務將被默默丟棄。
- **Recommendation:** 補充 DLQ 的監控告警規則，以及手動或自動的 Redrive 策略。

### [R5] 安全性：Prompt Injection 與內容清洗
- **Principle Reference:** Point 5 (Security)
- **Issue:** 爬蟲直接將外部網站內容餵給 LLM。若目標網站包含惡意 prompt injection 攻擊，可能會影響 LLM 的輸出結果或消耗大量 token。
- **Recommendation:** 在 `Analyzer Lambda` 實作輸入清洗 (Sanitization) 或截斷機制，限制傳入 LLM 的 context window 大小。

### [R7] 開發環境依賴管理 (Dependency Management)
- **Principle Reference:** Point 7 (Development Environment)
- **Issue:** Python 爬蟲常依賴 C-extensions (如 `lxml` 效能較好，或 `pandas` 若有資料處理)。單純的 Lambda Zip 上傳可能會遇到 OS 相容性問題。
- **Recommendation:** 建議明確指定使用 **Lambda Layers** 或改用 **Docker Container Image** 部署 Lambda，以確保開發機 (Windows/Mac) 與 AWS (Linux) 環境一致。

---

## 3. Nitpicks (Suggestions for Optimization)

### [N5] 網路架構與 VPC 成本
- **Principle Reference:** Point 6 (Cost) & Point 5 (Security)
- **Observation:** 文件未說明 Lambda 是否部署在 VPC 內。
- **Comment:** 
    - 若在 VPC 內：需考慮 **NAT Gateway** 的高昂成本 ($0.045/hr + 流量)，且對於爬蟲來說，固定 IP 可能反而容易被擋。
    - 若在 VPC 外：是最省錢且適合爬蟲的架構，但需確認 DynamoDB/SQS 的 IAM 權限設定無誤。
- **Suggestion:** 明確標註 "Lambda 將部署於 VPC 之外 (Public Subnet 或 No VPC)" 以節省成本，除非有特殊合規需求。

### [N8] DynamoDB Capacity Mode
- **Principle Reference:** Point 8 (Capacity)
- **Observation:** 未指定 DynamoDB 使用 Provisioned 還是 On-Demand 模式。
- **Comment:** 考量流量為 "每日/每週" 的脈衝式流量 (Spiky Traffic)，**On-Demand Mode** 會比 Provisioned 更划算且管理更簡單。
- **Suggestion:** 在 `D3` 決策中明確指定使用 On-Demand Capacity Mode。

### [N2] 模組化 - LLM Provider 設定
- **Principle Reference:** Point 2 (Modularity)
- **Observation:** `D5` 提到了 `LLMProvider` 抽象層，這很好。
- **Comment:** 建議將 `Prompt Template` 也從程式碼中抽離 (例如存放在 SSM Parameter Store 或獨立 config 檔)，以便不需重新部署 Lambda 即可調整 Prompt。

---

**Summary:**
本設計文件架構方向正確 (Serverless, 分層負責)，但在 **測試標準** 與 **可觀測性** 兩個關鍵運維面向嚴重不足。建議在進入實作階段前，先補齊上述 Gating Issues 的規劃。
