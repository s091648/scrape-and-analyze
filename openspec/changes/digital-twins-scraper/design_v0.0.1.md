## Context

這是一個全新的 Digital Twins 市場趨勢分析系統。目前沒有現有架構，需從零開始建立。

**系統約束**：
- 採用 AWS Serverless 架構（Lambda, DynamoDB, SQS, EventBridge）
- IaC 使用 AWS CDK with TypeScript
- 爬蟲邏輯使用 Python + BeautifulSoup
- 遵循 TDD 開發原則
- CI/CD 透過 GitHub Actions

**資料來源**：
- 每日來源：TechCrunch RSS, VentureBeat RSS, IoT World Today RSS, arXiv.org API
- 每週來源：NVIDIA Blog, Siemens Digital Industries, AWS IoT Blog, Azure IoT Blog

## Goals / Non-Goals

**Goals:**
- 建立可靠的定期爬蟲系統，自動收集 Digital Twins 相關內容
- 透過 LLM 自動化產生內容摘要與標籤
- 實現完善的錯誤處理機制，確保系統穩定性
- 保持 LLM 提供者的切換彈性
- 建立完整的 IaC 與 CI/CD 流程

**Non-Goals:**
- 不建立使用者介面（UI/Dashboard）
- 不實作即時串流處理
- 不處理付費牆或需要登入的內容
- 不建立資料分析或視覺化功能
- 不實作多語言支援（僅處理英文內容）

## Decisions

### D1: Lambda 分層架構

**決定**：將爬蟲與 LLM 解析分成兩個獨立的 Lambda Functions

**替代方案**：
- (A) 單一 Lambda 處理爬蟲 + LLM 解析
- (B) 三個 Lambda：爬蟲、內容擷取、LLM 解析

**選擇 (B) 兩個 Lambda 的理由**：
- 職責分離：爬蟲專注於資料收集，解析專注於 AI 處理
- 獨立擴展：LLM 呼叫較慢且成本高，可獨立調整並發數
- 錯誤隔離：爬蟲失敗不影響已收集資料的解析
- 重試彈性：可針對不同失敗類型設定不同重試策略

### D2: 爬蟲 Lambda 內部架構

**決定**：使用 Strategy Pattern 實作不同來源的爬蟲

```
ScraperLambda/
├── handler.py          # Lambda entry point
├── scrapers/
│   ├── base.py         # BaseScraper abstract class
│   ├── rss_scraper.py  # RSS 來源（TechCrunch, VentureBeat, IoT World Today）
│   ├── arxiv_scraper.py # arXiv API
│   └── blog_scraper.py  # 企業部落格
├── models/
│   └── article.py      # Article dataclass
└── storage/
    └── dynamodb.py     # DynamoDB 操作
```

**理由**：
- 統一介面方便新增來源
- 各爬蟲可獨立測試
- 符合 Open-Closed Principle

### D3: DynamoDB Table 設計

**決定**：兩個 Table，以 `article_id` 作為關聯鍵

**Table 1: ArticlesTable（原始內容）**
```
PK: article_id (UUID)
Attributes:
  - source: string (e.g., "techcrunch", "arxiv")
  - url: string
  - title: string
  - content: string
  - published_at: string (ISO 8601)
  - scraped_at: string (ISO 8601)
  - metadata: map (author, category, etc.)
```

**Table 2: AnalysisTable（解析結果）**
```
PK: analysis_id (UUID)
GSI: article_id-index (article_id)
Attributes:
  - article_id: string (foreign key reference)
  - tags: list<string>
  - pain_points: string
  - insights: string
  - innovations: string
  - analyzed_at: string (ISO 8601)
  - model_used: string (e.g., "claude-3-5-sonnet")
```

**理由**：
- 分離關注點：原始資料與解析結果獨立
- 可重新解析：更換 LLM 模型時可重新處理已有文章
- 查詢彈性：GSI 支援從 article_id 查詢解析結果

### D4: SQS 訊息傳遞

**決定**：使用 SQS Standard Queue + Dead Letter Queue

**訊息格式**：
```json
{
  "article_id": "uuid",
  "source": "techcrunch",
  "retry_count": 0
}
```

**配置**：
- Main Queue: visibility timeout 5 分鐘，max receive count 3
- DLQ: 保留 14 天

**理由**：
- 解耦爬蟲與解析 Lambda
- 自動重試失敗的解析任務
- DLQ 保留失敗訊息供後續處理

### D5: LLM Provider 抽象層

**決定**：建立 `LLMProvider` 抽象介面

```python
class LLMProvider(ABC):
    @abstractmethod
    def analyze(self, content: str, prompt: str) -> AnalysisResult:
        pass

class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        ...

class OpenAIProvider(LLMProvider):  # 未來擴展
    ...
```

**配置方式**：透過環境變數 `LLM_PROVIDER` 和 `LLM_MODEL` 切換

**理由**：
- 符合 Dependency Inversion Principle
- 方便測試（可 mock）
- 未來可輕鬆切換到 OpenAI、Bedrock 等

### D6: EventBridge 排程設計

**決定**：使用兩個 EventBridge Rules

- **Daily Rule**: `cron(0 8 * * ? *)` - 每天 UTC 08:00（台灣 16:00）
  - Target: Scraper Lambda with `{"schedule": "daily"}`

- **Weekly Rule**: `cron(0 8 ? * MON *)` - 每週一 UTC 08:00
  - Target: Scraper Lambda with `{"schedule": "weekly"}`

**理由**：
- 單一 Lambda 處理所有來源，透過 event 參數區分
- 固定時間方便監控與除錯
- 避免尖峰時段執行

### D7: 錯誤處理策略

**決定**：分層錯誤處理

| 錯誤類型 | 處理方式 |
|---------|---------|
| 單一來源爬蟲失敗 | 記錄錯誤，繼續處理其他來源 |
| DynamoDB 寫入失敗 | 重試 3 次，失敗則記錄並繼續 |
| SQS 發送失敗 | Lambda 重試機制處理 |
| LLM API 失敗 | SQS 重試，超過 3 次進 DLQ |
| Rate Limit | Exponential backoff |

**理由**：
- 部分失敗不應影響整體流程
- 保留失敗記錄供後續處理
- 符合 Graceful Degradation 原則

### D8: CDK 專案結構

**決定**：Monorepo 結構

```
/
├── cdk/                    # CDK TypeScript
│   ├── bin/
│   │   └── app.ts
│   ├── lib/
│   │   ├── scraper-stack.ts
│   │   └── constructs/
│   │       ├── scraper-lambda.ts
│   │       ├── analyzer-lambda.ts
│   │       ├── dynamodb-tables.ts
│   │       └── sqs-queues.ts
│   ├── package.json
│   └── tsconfig.json
├── lambda/                 # Python Lambda code
│   ├── scraper/
│   └── analyzer/
├── tests/                  # Python tests
└── .github/
    └── workflows/
        └── deploy.yml
```

**理由**：
- CDK 與 Lambda 程式碼放在同一 repo 方便管理
- Constructs 分離提高可維護性
- 測試與部署流程整合

### D9: GitHub Actions 權限設計

**決定**：使用 OIDC + 最小權限 IAM Role

**IAM Role 權限**：
- `cloudformation:*`（CDK 部署需要）
- `lambda:*`（函數部署）
- `dynamodb:CreateTable, UpdateTable, DeleteTable`
- `sqs:*`
- `events:*`
- `iam:PassRole`（僅限特定 Lambda execution roles）
- `s3:*` on CDK bootstrap bucket

**Trust Policy**：僅允許特定 GitHub repo 的 main branch

**理由**：
- OIDC 避免長期 credentials
- Least Privilege 原則
- 限制部署來源提高安全性

## Risks / Trade-offs

### R1: 爬蟲被封鎖
**風險**：目標網站可能封鎖 AWS IP range 或偵測爬蟲行為
**緩解**：
- 設定合理的 User-Agent
- 遵守 robots.txt
- 控制爬蟲頻率（每日/每週而非即時）
- 考慮未來使用 residential proxy（if needed）

### R2: Lambda Cold Start
**風險**：Lambda cold start 可能導致爬蟲超時
**緩解**：
- 使用 Provisioned Concurrency（如成本允許）
- 設定足夠的 timeout（建議 5 分鐘）
- 監控執行時間並調整

### R3: LLM 成本
**風險**：Claude API 呼叫成本可能超出預算
**緩解**：
- 監控 API 使用量
- 設定月度預算上限
- 考慮使用較便宜的模型（如 Haiku）處理簡單內容

### R4: 資料重複
**風險**：同一篇文章可能被多次爬取
**緩解**：
- 使用 URL 作為去重依據
- DynamoDB Conditional Write 避免重複

### R5: Schema 變更
**風險**：目標網站 HTML 結構變更導致爬蟲失敗
**緩解**：
- 建立監控與告警
- 爬蟲程式碼模組化，方便快速修復
- 考慮使用 LLM 輔助解析（未來優化）
