## Context

這是一個全新的 Digital Twins 市場趨勢分析系統。目前沒有現有架構，需從零開始建立。

**系統約束**：
- 採用 Railway 平台託管所有服務
- Database: PostgreSQL（Railway 託管）
- Scheduler: Railway Cron Jobs（按需執行，非 24/7）
- IaC: railway.toml + Git
- 爬蟲邏輯使用 Python + BeautifulSoup
- 遵循 TDD 開發原則

**資料來源**：
- 每日來源：TechCrunch RSS, VentureBeat RSS, IoT World Today RSS, arXiv.org API
- 每週來源：NVIDIA Blog, Siemens Digital Industries, AWS IoT Blog, Azure IoT Blog

## Goals / Non-Goals

**Goals:**
- 建立可靠的定期爬蟲系統，自動收集 Digital Twins 相關內容
- 透過 LLM 自動化產生內容摘要與標籤
- 實現完善的錯誤處理與重試機制，確保系統穩定性
- 保持 LLM 提供者的切換彈性
- 建立完善的可觀測性機制，支援端到端追蹤與問題診斷
- **最小化運行成本**，適合 Side Project 預算

**Non-Goals:**
- 不建立使用者介面（UI/Dashboard）
- 不實作即時串流處理
- 不處理付費牆或需要登入的內容
- 不建立資料分析或視覺化功能
- 不實作多語言支援（僅處理英文內容）

## Decisions

### D1: Railway 服務架構（Cron Job 模式）

**決定**：使用 Railway Cron Jobs 取代 24/7 Celery Workers

**架構變更理由（解決 [G2] 成本問題）**：
- 原設計使用 3 個 24/7 運行的 Celery Workers，對於「每天只執行一次」的任務是極大的浪費
- 預估成本：3 Containers × 512MB × 720h × ~$0.01 ≈ **$10-15/月**，遠超 Hobby Plan ($5)
- 改用 Cron Jobs 後，僅在執行期間計費，大幅降低成本

**新服務配置**：
```
Railway Project
├── Cron Jobs
│   ├── daily-scraper     # 每日 08:00 UTC 執行
│   └── weekly-scraper    # 每週一 08:00 UTC 執行
├── Databases
│   └── PostgreSQL        # Railway 託管
```

**執行模式**：
- **Monolithic Script**：單一 Python 腳本順序執行爬蟲 + 解析
- 爬取每篇文章後立即進行 LLM 解析（同步流程）
- 執行完畢後 Container 自動銷毀，僅計費執行期間

**成本效益**：
| 項目 | 原設計 (24/7 Celery) | 新設計 (Cron Jobs) |
|------|---------------------|-------------------|
| 月執行時間 | 720 小時 | ~2-4 小時 |
| 預估月成本 | $10-15 | < $1 |
| 架構複雜度 | 高（分散式） | 低（單體腳本） |

**理由**：
- 對於低頻 batch job，同步執行比分散式架構更經濟穩定
- 避免 24/7 運行的固定成本
- 簡化架構，降低維運複雜度

### D2: 單體腳本設計（解決 Dual-Write 問題）

**決定**：採用同步執行模式，在單一事務中完成爬蟲 + 解析

**問題背景（解決 [G1] 資料一致性風險）**：
- 原設計：寫入 DB → 發送 Redis 訊息 → 觸發解析
- 風險：若 Worker 在寫入 DB 後、發送訊息前崩潰，文章將成為「Zombie Record」（永遠未被解析）
- 原因：ON CONFLICT DO NOTHING 會跳過已存在的文章，包含其解析觸發

**新設計：並發處理流程**：
```python
# main.py
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

MAX_WORKERS = 3  # 並發數，避免過度消耗 LLM API quota
MAX_EXECUTION_TIME = 50 * 60  # 50 分鐘，預留 buffer
BATCH_SIZE = 50  # 每次執行最多處理篇數

def run_daily_scrape():
    """每日爬蟲主流程"""
    start_time = time.time()
    correlation_id = uuid.uuid4()

    # 1. 先自動重試近 24 小時內的失敗任務（Auto-Redrive）
    auto_redrive_recent_failures()

    # 2. 收集所有待處理文章
    sources = get_daily_sources()
    all_articles = []
    for source in sources:
        try:
            articles = scrape_source(source)
            all_articles.extend(articles)
        except Exception as e:
            logger.error("source_failed", source=source, error=str(e))
            continue

    # 3. Batch 限制
    articles_to_process = all_articles[:BATCH_SIZE]
    if len(all_articles) > BATCH_SIZE:
        logger.warning("batch_truncated",
                       total=len(all_articles), processed=BATCH_SIZE)

    # 4. 並發處理（使用 ThreadPoolExecutor）
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_article_safe, article, correlation_id): article
            for article in articles_to_process
        }
        for future in as_completed(futures):
            # 檢查執行時間
            if time.time() - start_time > MAX_EXECUTION_TIME:
                logger.warning("execution_timeout",
                               elapsed=time.time() - start_time)
                executor.shutdown(wait=False, cancel_futures=True)
                break

def auto_redrive_recent_failures():
    """自動重試 24 小時內的失敗任務"""
    cutoff = datetime.utcnow() - timedelta(hours=24)
    recent_failures = db.query(FailedTask).filter(
        FailedTask.resolved == False,
        FailedTask.failed_at >= cutoff
    ).all()

    for task in recent_failures:
        try:
            if task.article_id:
                article = db.query(Article).get(task.article_id)
                if article and not has_analysis(article.id):
                    analyze_and_save(article, uuid.uuid4())
                    task.resolved = True
                    task.resolved_at = datetime.utcnow()
                    db.session.commit()
        except Exception as e:
            logger.error("auto_redrive_failed", task_id=task.id, error=str(e))

def process_article_safe(article: Article, correlation_id: UUID):
    """安全處理單篇文章，含記憶體管理"""
    try:
        process_article(article, correlation_id)
    except Exception as e:
        logger.error("article_processing_failed",
                     article_url=article.url, error=str(e))
        record_failure('analyze', article_url=article.url, error=e)
    finally:
        # 記憶體管理：明確清理大型物件
        db.session.remove()  # 重置 session cache

def process_article(article: Article, correlation_id: UUID):
    """單篇文章處理：爬蟲 + 解析在同一流程中完成"""
    with db.session.begin():  # 單一事務
        # 1. 檢查是否已存在
        existing = db.query(Article).filter_by(url_hash=article.url_hash).first()
        if existing:
            # 已存在但未解析？補救處理
            if not has_analysis(existing.id):
                analyze_and_save(existing, correlation_id)
            return

        # 2. 儲存文章
        db.session.add(article)
        db.session.flush()  # 取得 article.id

        # 3. 立即解析並儲存（同一事務）
        analyze_and_save(article, correlation_id)
```

**原子性保證**：
- 使用 PostgreSQL Transaction 確保「儲存文章」與「儲存解析」的原子性
- 若解析失敗，整筆 Transaction Rollback，不會產生 Zombie Record
- 重試時會重新處理整篇文章

**補償機制（Belt and Suspenders）**：
```python
def scan_missing_analyses():
    """掃描並補救未解析的文章（可選的定期檢查）"""
    missing = db.query(Article).outerjoin(Analysis).filter(Analysis.id == None).all()
    for article in missing:
        try:
            analyze_and_save(article, uuid.uuid4())
        except Exception as e:
            logger.error("remediation_failed", article_id=article.id, error=str(e))
```

**理由**：
- 同步執行天然解決 Dual-Write 問題
- PostgreSQL Transaction 提供 ACID 保證
- ThreadPoolExecutor 並發處理縮短總執行時間（不增加架構複雜度）
- Auto-Redrive 機制減少人工介入
- 明確的 batch size 與 timeout 防止執行過長
- `db.session.remove()` 避免記憶體洩漏累積

### D3: 專案結構

**決定**：簡化的單體應用結構

```
/
├── src/
│   ├── __init__.py
│   ├── main.py             # 主程式入口（Cron Job 執行）
│   ├── config.py           # 環境變數與配置
│   ├── database.py         # SQLAlchemy 連線管理
│   ├── models/
│   │   ├── __init__.py
│   │   ├── article.py      # SQLAlchemy Article model
│   │   └── analysis.py     # SQLAlchemy Analysis model
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py         # BaseScraper abstract class
│   │   ├── rss_scraper.py  # RSS 來源
│   │   ├── arxiv_scraper.py # arXiv API
│   │   └── blog_scraper.py  # 企業部落格
│   ├── analyzers/
│   │   ├── __init__.py
│   │   ├── llm_provider.py # LLM Provider 抽象層
│   │   └── claude.py       # Claude 實作
│   └── utils/
│       ├── __init__.py
│       ├── sanitizer.py    # HTML 清洗
│       └── logging.py      # Structured logging
├── tests/
│   ├── unit/
│   └── integration/
├── Dockerfile
├── requirements.txt
├── railway.toml
└── .env.example
```

**啟動命令**：
```bash
# 每日爬蟲
python -m src.main daily

# 每週爬蟲
python -m src.main weekly
```

**理由**：
- 移除 Celery/Redis 相關依賴，簡化架構
- 單一入口點，易於測試與除錯
- 透過 CLI 參數區分每日/每週任務

### D4: PostgreSQL Schema 設計

**決定**：兩張表，以 `article_id` 作為關聯鍵

**Table 1: articles（原始內容）**
```sql
CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT UNIQUE NOT NULL,
    url_hash VARCHAR(64) NOT NULL,  -- SHA-256 for dedup
    source VARCHAR(50) NOT NULL,    -- e.g., 'techcrunch', 'arxiv'
    title TEXT NOT NULL,
    content TEXT NOT NULL,          -- 已清洗的純文字
    published_at TIMESTAMPTZ,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB,                 -- author, category, etc.
    correlation_id UUID NOT NULL,   -- 追蹤用

    CONSTRAINT unique_url_hash UNIQUE (url_hash)
);

CREATE INDEX idx_articles_source ON articles(source);
CREATE INDEX idx_articles_scraped_at ON articles(scraped_at);
CREATE INDEX idx_articles_correlation_id ON articles(correlation_id);
```

**Table 2: analyses（解析結果）**
```sql
CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id UUID NOT NULL REFERENCES articles(id),
    correlation_id UUID NOT NULL,
    tags TEXT[] NOT NULL,
    pain_points TEXT,
    insights TEXT,
    innovations TEXT,
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    model_used VARCHAR(100) NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,

    CONSTRAINT unique_article_analysis UNIQUE (article_id)
);

CREATE INDEX idx_analyses_article_id ON analyses(article_id);
CREATE INDEX idx_analyses_analyzed_at ON analyses(analyzed_at);
```

**Table 3: failed_tasks（失敗記錄，用於手動補救）**
```sql
CREATE TABLE failed_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR(50) NOT NULL,  -- 'scrape' | 'analyze'
    article_url TEXT,
    article_id UUID REFERENCES articles(id),
    exception_type VARCHAR(200),
    exception_message TEXT,
    failed_at TIMESTAMPTZ DEFAULT NOW(),
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_failed_tasks_resolved ON failed_tasks(resolved);
```

**去重機制**：
- 使用 URL 的 SHA-256 Hash 作為 `url_hash`
- `UNIQUE (url_hash)` constraint 確保不重複寫入
- 查詢時檢查是否已有對應的 analysis，無則補做

**PostgreSQL 連線管理（應對 Railway 連線數限制）**：
```python
# src/database.py
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

# Railway Hobby Plan 通常限制 max_connections=20
# 使用 NullPool 避免連線池耗盡問題
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,  # 每次查詢新建連線，用完即關
)
```

**理由**：
- PostgreSQL 支援完整的 ACID 事務
- NullPool 確保不會耗盡 Railway 的連線數限制
- failed_tasks 表提供手動補救的能力

### D5: Railway Cron Jobs 排程配置

**決定**：使用 Railway Cron Jobs 觸發腳本執行

**railway.toml 配置（解決 [G3] Health Check 問題）**：
```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

# 注意：Cron Jobs 不需要 healthcheck
# Railway 會自動偵測 process 結束
# 不設定 healthcheckPath，避免部署失敗
```

**Cron Jobs 設定（透過 Railway Dashboard）**：

| Job Name | Schedule | Command |
|----------|----------|---------|
| daily-scraper | `0 8 * * *` | `python -m src.main daily` |
| weekly-scraper | `0 8 * * 1` | `python -m src.main weekly` |

**理由**：
- Cron Jobs 僅在執行期間計費
- 不需要 Health Check（執行完畢自動結束）
- 避免 24/7 運行的浪費

### D6: 錯誤處理與重試策略

**決定**：應用層重試 + 失敗記錄

**重試機制**：
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
)
def call_llm_api(content: str) -> AnalysisResult:
    """LLM API 呼叫，自動重試"""
    ...

def process_article_safe(article: Article, correlation_id: UUID):
    """安全處理單篇文章，失敗記錄但不中斷"""
    try:
        process_article(article, correlation_id)
    except Exception as e:
        logger.error("article_processing_failed",
                     article_url=article.url, error=str(e))
        record_failure('analyze', article_url=article.url,
                       article_id=article.id, error=e)
```

**錯誤處理策略**：
| 錯誤類型 | 處理方式 |
|---------|---------|
| 單一來源爬蟲失敗 | 記錄錯誤，繼續處理其他來源 |
| 單篇文章處理失敗 | 記錄到 failed_tasks，繼續下一篇 |
| LLM API 失敗 | tenacity 重試 3 次 with backoff |
| Rate Limit (429) | Exponential backoff，最長 60 秒 |
| 重試耗盡 | 寫入 failed_tasks，繼續處理 |
| 執行超時 | 記錄 warning，graceful shutdown |

**Auto-Redrive 機制**：
- 每次 Cron Job 啟動時，自動重試 24 小時內的失敗任務
- 成功後標記 `resolved = True`
- 減少人工介入需求

**手動補救腳本**（處理超過 24 小時的失敗）：
```bash
# 補救所有未解決的失敗任務
python -m src.main remediate
```

**理由**：
- tenacity 提供簡潔的重試語法
- 失敗不中斷整體流程（Graceful Degradation）
- Auto-Redrive 自動處理近期失敗
- failed_tasks 表支援手動補救舊任務

### D7: LLM Provider 抽象層

**決定**：建立 `LLMProvider` 抽象介面

```python
# src/analyzers/llm_provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class AnalysisResult:
    tags: list[str]
    pain_points: str
    insights: str
    innovations: str
    input_tokens: int
    output_tokens: int

class LLMProvider(ABC):
    @abstractmethod
    def analyze(self, content: str, prompt: str) -> AnalysisResult:
        pass

# src/analyzers/claude.py
class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def analyze(self, content: str, prompt: str) -> AnalysisResult:
        ...
```

**配置方式**：
- `LLM_PROVIDER` 環境變數：選擇 provider（claude, openai 等）
- `LLM_MODEL` 環境變數：選擇模型
- `LLM_API_KEY` 環境變數：API Key（Railway 變數管理）
- Prompt Template：儲存於 `src/prompts/analysis.txt`

**理由**：
- 符合 Dependency Inversion Principle
- 方便測試（可 mock）
- 未來可輕鬆切換到 OpenAI、Bedrock 等

### D8: 輸入清洗與安全防護

**決定**：兩階段清洗

**階段一：Scraper（寫入 DB 前）**
```python
from bs4 import BeautifulSoup

MAX_CONTENT_LENGTH = 50_000  # 約 50KB，純文字長度

def sanitize_content(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, 'html.parser')
    # 移除非內容元素
    for tag in soup(['script', 'style', 'nav', 'footer', 'aside']):
        tag.decompose()
    text = soup.get_text(separator='\n', strip=True)

    if len(text) > MAX_CONTENT_LENGTH:
        text = text[:MAX_CONTENT_LENGTH] + "\n[Content truncated]"
    return text
```

**階段二：Analyzer（呼叫 LLM 前）**
- Prompt 使用明確的 delimiter 區隔系統指令與用戶內容
- 輸出驗證 JSON Schema

**Prompt 結構**：
```
<system>
你是一個專業的技術分析師。請分析以下文章內容...
</system>

<article>
{sanitized_content}
</article>

請以 JSON 格式輸出分析結果...
```

**理由**：
- 防範 Prompt Injection
- 限制 token 消耗，控制成本
- 驗證輸出格式確保資料品質

### D9: 可觀測性架構

**決定**：Structured Logging + Grafana Cloud

**Log 結構（JSON 格式）**：
```python
import structlog

logger = structlog.get_logger()

logger.info(
    "article_scraped",
    correlation_id=str(correlation_id),
    source="techcrunch",
    article_id=str(article_id),
    content_length=len(content),
)
```

**Grafana Cloud 整合**：
- Logs：透過 Grafana Loki（Railway logs 轉發）
- Metrics：從 logs 中萃取（Log-based metrics）
- Alerts：Grafana Alerting

**關鍵 Metrics（從 Logs 萃取）**：
| Metric | 說明 |
|--------|------|
| articles_scraped_total | 爬取文章總數（按 source） |
| articles_analyzed_total | 解析文章總數 |
| llm_latency_seconds | LLM API 呼叫延遲 |
| llm_tokens_total | Token 使用量（input/output） |
| task_failures_total | 任務失敗數 |

**告警規則**：
| 條件 | 動作 |
|------|------|
| task_failures > 5 in single run | Email 通知 |
| No scrape log in 25h | Email 通知（每日排程異常） |
| Cron job execution > 30 min | Email 通知 |

**理由**：
- Structured logging 便於查詢與分析
- Grafana Cloud 免費版足夠 MVP 使用
- correlation_id 追蹤文章完整生命週期

### D10: Railway 部署配置

**決定**：使用 railway.toml + Cron Jobs（無 Health Check）

**railway.toml**：
```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

# Cron Jobs 不需要 deploy 配置
# 不設定 healthcheckPath（Cron Job 執行完即結束，無 HTTP Server）
```

**Dockerfile**：
```dockerfile
FROM python:3.11-slim

# 確保 logs 即時輸出到 Railway Console
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# 預設入口（可被 Cron Job command 覆蓋）
CMD ["python", "-m", "src.main", "daily"]
```

**環境變數（Railway Variables）**：
```
DATABASE_URL=postgresql://...  # Railway 自動注入
LLM_API_KEY=sk-...
LLM_PROVIDER=claude
LLM_MODEL=claude-sonnet-4-20250514
SENTRY_DSN=https://...
```

**理由**：
- 移除 healthcheckPath（Cron Job 無需 HTTP Server，解決 [G3]）
- 簡化 Dockerfile，無需額外的 health endpoint
- Railway 自動處理 database URL 注入

## Risks / Trade-offs

### R1: 爬蟲被封鎖
**風險**：目標網站可能封鎖爬蟲或使用 Cloudflare Anti-Bot
**緩解**：
- 設定合理的 User-Agent
- 遵守 robots.txt
- 控制爬蟲頻率（每日/每週）
- Railway 使用動態 IP

**預留升級路徑**：
- Headless Browser（Playwright）
- 第三方 Proxy Service

### R2: 執行時間過長 (Timeout)
**風險**：長時間執行可能被 Railway 或 Docker Runtime 中斷
**緩解**：
- **Batch Size 限制**：每次最多處理 50 篇，超出部分等下次執行
- **Max Execution Time**：程式執行超過 50 分鐘自動 graceful shutdown
- **ThreadPoolExecutor 並發**：max_workers=3 並發處理，縮短總時間
- 預估每日 ~50 篇，並發處理約 5-10 分鐘可完成

**權衡**：使用輕量並發（ThreadPoolExecutor）而非複雜的分散式架構

### R7: 記憶體溢出 (OOM)
**風險**：長時間運行累積大型物件導致 OOM（Railway Hobby Plan 記憶體有限）
**緩解**：
- 每篇文章處理完後呼叫 `db.session.remove()` 重置 SQLAlchemy session cache
- 避免在迴圈中累積大型 HTML string
- Batch size 限制單次執行的記憶體峰值

### R3: LLM 成本
**風險**：Claude API 呼叫成本可能超出預算
**緩解**：
- 監控 token 使用量
- 設定月度預算上限
- 內容截斷限制 token 消耗
- 考慮使用較便宜的模型（如 Haiku）

### R4: PostgreSQL 連線數
**風險**：Railway Hobby Plan 限制 max_connections ~20
**緩解**：
- 使用 SQLAlchemy NullPool，每次查詢新建連線
- Cron Job 單一 process 執行，不會同時佔用多個連線
- 若需要，可限制 pool_size

### R5: Schema 變更
**風險**：目標網站 HTML 結構變更導致爬蟲失敗
**緩解**：
- 建立監控與告警
- 爬蟲程式碼模組化（Strategy Pattern）
- 快速修復與部署

### R6: Prompt Injection
**風險**：外部網站內容可能包含惡意 prompt injection
**緩解**：
- 輸入清洗（HTML stripping, truncation）
- 結構化 prompt with delimiters
- 輸出 JSON Schema 驗證

## Test Plan

### 單元測試
| 測試案例 | 驗證條件 |
|---------|---------|
| RSS 解析成功 | 正確提取 title, content, url |
| arXiv API 回應正常 | 正確解析 JSON 回應 |
| HTML 內容清洗 | 正確移除 script/style |
| 內容截斷 | 超過 50KB 正確截斷 |
| LLM 回應正常 | 正確解析 JSON，驗證 schema |
| Provider 切換 | Mock 驗證不同 provider 呼叫 |
| 去重邏輯 | 重複 URL 不重複寫入 |
| 補救邏輯 | 已存在但未解析的文章會被補做 |
| Auto-Redrive | 24h 內失敗任務自動重試 |
| Batch 限制 | 超過 BATCH_SIZE 的文章被截斷 |
| Timeout 處理 | 超過 MAX_EXECUTION_TIME 自動停止 |

### 整合測試
使用 Docker Compose 模擬完整環境：
- PostgreSQL

| 測試案例 | 驗證條件 |
|---------|---------|
| 完整流程 | 爬蟲 → 儲存 → 解析 → 儲存結果 |
| Transaction 原子性 | 解析失敗時整筆 Rollback |
| 重試機制 | 模擬 LLM API 失敗後正確重試 |
| 失敗記錄 | 失敗正確寫入 failed_tasks |
| 連線管理 | 執行完畢後無殘留連線 |
