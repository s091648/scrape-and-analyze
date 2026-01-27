## Why

需要建立一個自動化的市場趨勢分析系統，透過定期爬蟲收集 Digital Twins（數位孿生）相關的技術文章、研究論文與產業動態，並利用 LLM 進行內容解析與洞見萃取，以支援市場分析決策。

## What Changes

- 新增 **每日爬蟲排程**：從科技新聞 RSS（TechCrunch、VentureBeat）、arXiv.org API、IoT World Today RSS 抓取 Digital Twins 相關內容
- 新增 **每週爬蟲排程**：從企業技術部落格（NVIDIA Blog、Siemens Digital Industries、AWS IoT Blog、Azure IoT Blog）抓取 Digital Twins 相關內容
- 新增 **原始資料儲存**：將爬蟲抓取的文章內容與 metadata 儲存至 DynamoDB
- 新增 **LLM 內容解析**：透過 Claude API 解析文章本文，產生標籤（tags）、痛點、洞見、創新等摘要
- 新增 **解析結果儲存**：將 LLM 解析結果儲存至獨立的 DynamoDB table，並與原始資料建立關聯
- 新增 **錯誤處理機制**：實作 Dead Letter Queue 處理爬蟲失敗與 LLM 解析失敗的情況
- 新增 **IaC 配置**：使用 AWS CDK (TypeScript) 定義所有雲端資源
- 新增 **CI/CD Pipeline**：透過 GitHub Actions 實現自動化部署

## Capabilities

### New Capabilities

- `rss-scraper`: RSS 來源爬蟲功能，支援 TechCrunch、VentureBeat、IoT World Today 的每日排程爬蟲
- `api-scraper`: API 來源爬蟲功能，支援 arXiv.org API 的每日排程查詢
- `blog-scraper`: 企業部落格爬蟲功能，支援 NVIDIA、Siemens、AWS、Azure 部落格的每週排程爬蟲
- `content-storage`: 原始爬蟲內容與 metadata 的 DynamoDB 儲存功能
- `llm-analyzer`: LLM 內容解析功能，支援標籤產生、痛點/洞見/創新摘要，並保持模型切換彈性
- `analysis-storage`: LLM 解析結果的 DynamoDB 儲存功能，與原始內容建立關聯
- `error-handling`: 錯誤處理與 Dead Letter Queue 機制
- `scheduler`: EventBridge 排程觸發機制（每日/每週）
- `cdk-infrastructure`: AWS CDK TypeScript IaC 配置
- `cicd-pipeline`: GitHub Actions CI/CD 部署流程

### Modified Capabilities

（無現有功能需要修改，這是全新專案）

## Impact

### 雲端資源（AWS）
- Lambda Functions x2（爬蟲 Lambda、LLM 解析 Lambda）
- DynamoDB Tables x2（原始內容、解析結果）
- EventBridge Rules（每日/每週排程）
- SQS Queues（Lambda 間通訊、Dead Letter Queue）
- IAM Roles & Policies

### 外部依賴
- Claude API（Anthropic）- LLM 解析服務
- RSS Feeds: TechCrunch, VentureBeat, IoT World Today
- arXiv.org API
- 企業部落格: NVIDIA, Siemens, AWS IoT, Azure IoT

### 開發依賴
- Python: beautifulsoup4, requests, boto3
- TypeScript: aws-cdk-lib
- GitHub Actions: AWS credentials, deployment permissions

### 成本考量
- Lambda 執行時間與記憶體
- DynamoDB 讀寫容量
- SQS 訊息數量
- Claude API 呼叫次數
