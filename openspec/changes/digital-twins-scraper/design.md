## Context

這是一個全新的 Digital Twins 市場趨勢分析系統。目前沒有現有架構，需從零開始建立。

**系統約束**：
- 採用 AWS Serverless 架構（Lambda, DynamoDB, SQS, EventBridge）
- Lambda 部署於 **VPC 之外**（無需 NAT Gateway，降低成本且避免固定 IP 被封鎖）
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
- **建立完善的可觀測性機制**，支援端到端追蹤與問題診斷

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

**選擇兩個 Lambda 的理由**：
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

**決定**：兩個 Table，以 `article_id` 作為關聯鍵，使用 **On-Demand Capacity Mode**

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
  - correlation_id: string (用於追蹤整個處理流程)
```

**Table 2: AnalysisTable（解析結果）**
```
PK: analysis_id (UUID)
GSI: article_id-index (article_id)
Attributes:
  - article_id: string (foreign key reference)
  - correlation_id: string (用於追蹤整個處理流程)
  - tags: list<string>
  - pain_points: string
  - insights: string
  - innovations: string
  - analyzed_at: string (ISO 8601)
  - model_used: string (e.g., "claude-3-5-sonnet")
```

**Capacity Mode: On-Demand**
- 考量流量為「每日/每週」的脈衝式流量 (Spiky Traffic)
- On-Demand 比 Provisioned 更划算且管理更簡單
- 無需預估和調整 RCU/WCU

**理由**：
- 分離關注點：原始資料與解析結果獨立
- 可重新解析：更換 LLM 模型時可重新處理已有文章
- 查詢彈性：GSI 支援從 article_id 查詢解析結果

### D4: SQS 訊息傳遞與 DLQ 處理

**決定**：使用 SQS Standard Queue + Dead Letter Queue，並配置完整的監控與重驅動機制

**訊息格式**：
```json
{
  "article_id": "uuid",
  "correlation_id": "uuid",
  "source": "techcrunch",
  "retry_count": 0
}
```

**配置**：
- Main Queue: visibility timeout 5 分鐘，max receive count 3
- DLQ: 保留 14 天

**DLQ 監控與處理**：
- **CloudWatch Alarm**: 當 `ApproximateNumberOfMessagesVisible > 0` 時觸發告警
- **告警通知**: 透過 SNS 發送 Email 通知維運人員
- **Redrive 策略**:
  - 手動 Redrive：透過 AWS Console 或 CLI 執行 `start-message-move-task`
  - 維運人員需先排查失敗原因，修復後再重驅動

**理由**：
- 解耦爬蟲與解析 Lambda
- 自動重試失敗的解析任務
- DLQ 監控確保失敗訊息不會被默默丟棄

### D5: LLM Provider 抽象層

**決定**：建立 `LLMProvider` 抽象介面，並將 Prompt Template 外部化

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

**配置方式**：
- `LLM_PROVIDER` 環境變數：選擇 provider（claude, openai 等）
- `LLM_MODEL` 環境變數：選擇模型
- **Prompt Template**: 儲存於 SSM Parameter Store (`/digital-twins-scraper/prompts/analysis`)
  - 可不重新部署 Lambda 即可調整 Prompt
  - 支援版本控制與回滾

**理由**：
- 符合 Dependency Inversion Principle
- 方便測試（可 mock）
- 未來可輕鬆切換到 OpenAI、Bedrock 等
- Prompt 外部化提高維運彈性

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
| 單一來源爬蟲失敗 | 記錄錯誤（含 correlation_id），繼續處理其他來源 |
| DynamoDB 寫入失敗 | 重試 3 次，失敗則記錄並繼續 |
| SQS 發送失敗 | Lambda 重試機制處理 |
| LLM API 失敗 | SQS 重試，超過 3 次進 DLQ，觸發告警 |
| Rate Limit | Exponential backoff |

**理由**：
- 部分失敗不應影響整體流程
- 保留失敗記錄供後續處理
- 符合 Graceful Degradation 原則

### D8: CDK 專案結構與 Lambda 部署方式

**決定**：Monorepo 結構，Lambda 使用 **Docker Container Image** 部署

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
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── ...
│   └── analyzer/
│       ├── Dockerfile
│       ├── requirements.txt
│       └── ...
├── tests/                  # Python tests
└── .github/
    └── workflows/
        └── deploy.yml
```

**Lambda 部署方式: Docker Container Image**
- 避免 Python C-extensions（如 lxml）在不同 OS 間的相容性問題
- 確保開發機 (Windows/Mac) 與 AWS (Linux) 環境一致
- 最大支援 10GB image size，足夠包含所有依賴

**理由**：
- CDK 與 Lambda 程式碼放在同一 repo 方便管理
- Constructs 分離提高可維護性
- 測試與部署流程整合
- Docker 確保環境一致性

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
- `ecr:*`（Docker image push）
- `ssm:GetParameter, PutParameter`（Prompt Template 管理）

**Trust Policy**：僅允許特定 GitHub repo 的 main branch

**理由**：
- OIDC 避免長期 credentials
- Least Privilege 原則
- 限制部署來源提高安全性

### D10: 可觀測性架構 (Observability)

**決定**：實作 Structured Logging with Correlation IDs + CloudWatch Dashboards

**Correlation ID 機制**：
- 爬蟲 Lambda 為每次執行產生一個 `execution_id`
- 每篇文章產生一個 `correlation_id`，貫穿整個處理流程
- 所有 Log 和 SQS 訊息都包含 `correlation_id`

**Log 結構 (JSON 格式)**：
```json
{
  "timestamp": "2024-01-27T08:00:00Z",
  "level": "INFO",
  "correlation_id": "uuid",
  "execution_id": "uuid",
  "source": "techcrunch",
  "event": "article_scraped",
  "article_id": "uuid",
  "message": "Successfully scraped article"
}
```

**CloudWatch 配置**：
- **Log Groups**:
  - `/aws/lambda/digital-twins-scraper`
  - `/aws/lambda/digital-twins-analyzer`
- **Retention**: 30 天
- **Log Format**: JSON（便於 CloudWatch Insights 查詢）

**CloudWatch Insights 查詢範例**：
```
fields @timestamp, correlation_id, event, message
| filter correlation_id = "specific-uuid"
| sort @timestamp asc
```

**CloudWatch Alarms**：
| Metric | Condition | Action |
|--------|-----------|--------|
| Lambda Errors | > 3 in 5 min | SNS Email |
| DLQ Message Count | > 0 | SNS Email |
| Lambda Duration | p99 > 4 min | SNS Email |

**替代方案考量**：
- AWS X-Ray：提供更完整的 distributed tracing，但對於每日/每週執行的 batch job，Structured Logging 已足夠
- 若未來需要更細緻的追蹤，可啟用 X-Ray

**理由**：
- 透過 correlation_id 可追蹤單一文章的完整生命週期
- JSON 格式便於程式化查詢
- 適當的告警確保問題被及時發現

### D11: 輸入清洗與安全防護

**決定**：在 Analyzer Lambda 實作輸入清洗機制，防範 Prompt Injection

**清洗策略**：
1. **Content Truncation**: 限制傳入 LLM 的內容長度（最大 50,000 字元）
2. **HTML Tag Stripping**: 移除所有 HTML 標籤，只保留純文字
3. **Special Character Filtering**: 移除可能干擾 prompt 的特殊字元序列
4. **Prompt Structure**: 使用明確的 delimiter 區隔系統指令與用戶內容

**Prompt 結構範例**：
```
<system>
你是一個專業的技術分析師。請分析以下文章內容，提取...
</system>

<article>
{sanitized_content}
</article>

請以 JSON 格式輸出分析結果...
```

**輸出驗證**：
- 驗證 LLM 輸出符合預期的 JSON Schema
- 若輸出格式錯誤，記錄警告並標記該分析為失敗

**理由**：
- 外部網站內容可能包含惡意 prompt injection
- 限制 token 消耗，控制成本
- 結構化 prompt 降低 injection 成功率

## Test Plan

### 測試策略

**覆蓋率目標**：核心業務邏輯 > 80%

### 單元測試 (Unit Tests)

**爬蟲 Lambda**:
| 測試案例 | 驗證條件 |
|---------|---------|
| RSS 解析成功 | 正確提取 title, content, url, published_at |
| RSS 格式錯誤 | 拋出 `ParseError`，包含來源資訊 |
| arXiv API 回應正常 | 正確解析 JSON 回應 |
| arXiv API 回傳空結果 | 回傳空 list，不拋錯 |
| 部分來源失敗 | 成功來源繼續處理，失敗來源記錄錯誤 |
| URL 重複檢查 | Conditional Write 拋出 `DuplicateError` |

**解析 Lambda**:
| 測試案例 | 驗證條件 |
|---------|---------|
| LLM 回應正常 | 正確解析 JSON，驗證 schema |
| LLM 回應格式錯誤 | 標記為解析失敗，記錄原始回應 |
| LLM 回應為空 | 標記為解析失敗，不存入 DB |
| 內容清洗 | 移除 HTML tags，截斷超長內容 |
| Provider 切換 | Mock 驗證不同 provider 的呼叫 |

**輸出驗證 (JSON Schema)**：
```json
{
  "type": "object",
  "required": ["tags", "pain_points", "insights", "innovations"],
  "properties": {
    "tags": {"type": "array", "items": {"type": "string"}},
    "pain_points": {"type": "string"},
    "insights": {"type": "string"},
    "innovations": {"type": "string"}
  }
}
```

### 整合測試 (Integration Tests)

**使用 LocalStack 模擬 AWS 服務**：
- DynamoDB: 測試 CRUD 操作、Conditional Write、GSI 查詢
- SQS: 測試訊息發送、接收、DLQ 路由

| 測試案例 | 驗證條件 |
|---------|---------|
| 爬蟲 -> DynamoDB -> SQS 流程 | 文章正確存入 DB，訊息正確進入 Queue |
| SQS -> 解析 Lambda -> DynamoDB | 訊息正確觸發 Lambda，結果正確存入 |
| 重試機制 | 模擬失敗後，訊息重新進入 Queue |
| DLQ 路由 | 超過重試次數後，訊息進入 DLQ |

### E2E 測試 (End-to-End)

**在 Staging 環境執行**：
- 使用真實 AWS 服務
- 使用測試用的 LLM API key（設定較低的 rate limit）
- 驗證完整流程從 EventBridge 觸發到最終分析結果

### CI/CD 整合

```yaml
# .github/workflows/test.yml
- Unit Tests: pytest tests/unit --cov=lambda --cov-fail-under=80
- Integration Tests: pytest tests/integration (with LocalStack)
- E2E Tests: 僅在 main branch merge 時執行
```

## Risks / Trade-offs

### R1: 爬蟲被封鎖
**風險**：目標網站可能封鎖 AWS IP range 或偵測爬蟲行為
**緩解**：
- 設定合理的 User-Agent
- 遵守 robots.txt
- 控制爬蟲頻率（每日/每週而非即時）
- Lambda 部署於 VPC 外，使用動態 IP
- 考慮未來使用 residential proxy（if needed）

### R2: Lambda Timeout
**風險**：爬蟲或解析任務執行時間過長
**緩解**：
- 設定足夠的 timeout：爬蟲 Lambda 10 分鐘，解析 Lambda 5 分鐘
- 監控執行時間，設定 p99 > 4 分鐘告警
- **不使用 Provisioned Concurrency**：對於每日/每週執行的 batch job，cold start (< 10秒) 影響可忽略

### R3: LLM 成本
**風險**：Claude API 呼叫成本可能超出預算
**緩解**：
- 監控 API 使用量
- 設定月度預算上限
- 考慮使用較便宜的模型（如 Haiku）處理簡單內容
- 內容截斷限制 token 消耗

### R4: 資料重複
**風險**：同一篇文章可能被多次爬取
**緩解**：
- 使用 URL 作為去重依據
- DynamoDB Conditional Write 避免重複

### R5: Schema 變更
**風險**：目標網站 HTML 結構變更導致爬蟲失敗
**緩解**：
- 建立監控與告警（Lambda Errors）
- 爬蟲程式碼模組化，方便快速修復
- 考慮使用 LLM 輔助解析（未來優化）

### R6: Prompt Injection
**風險**：外部網站內容可能包含惡意 prompt injection 攻擊
**緩解**：
- 輸入清洗（HTML stripping, truncation）
- 結構化 prompt with delimiters
- 輸出 JSON Schema 驗證
- 監控異常的 token 消耗
