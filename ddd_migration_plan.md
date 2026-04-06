# DDD Migration + HTTP Infrastructure Plan

## 背景與問題診斷

### 現行架構的核心問題

| 問題 | 位置 | 影響 |
|------|------|------|
| `main.py` 400 行包辦一切 | `src/main.py` | 難以測試、職責爆炸 |
| 所有 scraper 直呼 `requests.get()` | `rss/blog/arxiv/html_parser` | 無統一 retry、無 UA rotation、易被 block |
| UA 硬編 `"Digital-Twins-Scraper/1.0"` | 全部 HTTP caller | 最容易被偵測的 bot fingerprint |
| rate limit 只靠 `time.sleep(5)` in worker | `worker.py:78` | global delay，不是 per-domain |
| `arxiv_scraper` 有自己的 ad-hoc retry | `arxiv_scraper.py:83-106` | 邏輯分散，各 scraper 不一致 |
| `HtmlArticleParser.fetch_and_parse()` 直接 HTTP | `html_parser.py:39-58` | 跟 scraper 一樣沒有任何防護 |
| `config.py` 直接查 DB | `config.py:13-53` | infra 滲入 config；跨層耦合 |
| `arxiv_scraper.py` 查 DB 取 keywords | `arxiv_scraper.py:61-72` | domain logic 被 scraper 持有 |
| 無 Repository 抽象 | 全部 | SQLAlchemy model 直接暴露給 use case |

---

## 目標架構

```
src/
├── interfaces/cli/main.py          # 超薄 entry point（目標 < 40 行）
├── app/use_cases/                  # orchestration only
│   ├── run_scraper.py
│   ├── process_article.py
│   └── analyze_article.py
├── domain/                         # 純業務邏輯，零外部依賴
│   ├── entities/
│   ├── value_objects/
│   ├── services/dedup_service.py
│   └── repositories/               # ABC interfaces only
├── infrastructure/
│   ├── http/                       # ⭐ 本次新增核心
│   │   ├── http_client.py          # 統一入口（proxy + UA + rate + retry）
│   │   ├── rate_limiter.py         # per-domain token bucket
│   │   ├── retry.py                # tenacity policy（429/403/5xx）
│   │   └── user_agent.py           # realistic UA pool + rotation
│   ├── persistence/
│   │   ├── db.py                   # 原 database.py
│   │   └── sqlalchemy_repos/
│   └── observability/              # 原 src/observability/
├── ingestion/                      # Scraper bounded context
│   ├── scrapers/
│   ├── parsers/
│   └── models/scraped_article.py
├── pipeline/                       # 原 scrapers/strategy/
│   ├── dispatcher.py
│   ├── worker.py
│   └── task.py
├── analysis/                       # LLM bounded context
│   ├── providers/
│   └── strategies/
├── notifications/                  # 維持現狀
├── config/
│   ├── settings.py                 # env vars only，不碰 DB
│   └── providers.py                # providers.toml loader
└── utils/                          # sanitizer, logging（保留）
```

---

## Phase 執行計畫

> **原則**：每個 Phase 結束後系統仍可正常運行，不做 big-bang rewrite。  
> **Phase 1 可立即獨立上線**，直接解決 429/403 而不需等其他 Phase。

---

### Phase 1 — Infrastructure/HTTP 層（最高優先）

**目標**：建立統一 HTTP 客戶端，讓所有 HTTP call 改用它，一次性系統化解決 UA/retry/rate limit。

#### 1-A：`infrastructure/http/user_agent.py`

**職責**：維護 realistic browser UA 池，提供 per-domain 輪換。

```python
_UA_POOL = [
    # Chrome 123/124 on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox on Windows / Linux
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    # ... 共 15-20 條
]

class UserAgentPool:
    def get(self, domain: str | None = None) -> str:
        # per-domain 記憶上次 UA，避免同 session 亂換（部分站偵測 UA 不一致）
        ...
    def rotate(self, domain: str) -> str:
        # 強制換下一條 UA；收到 403 時由 http_client 呼叫
        ...
```

設計要點：
- per-domain 記憶使用中的 UA index（`threading.Lock` 保護）
- `rotate()` 時強制跳到下一條，使用 cyclic index

#### 1-B：`infrastructure/http/rate_limiter.py`

**職責**：per-domain token bucket，thread-safe。

```python
_DEFAULT_RPM: float = 10.0
_DOMAIN_RPM_OVERRIDES: dict[str, float] = {
    "export.arxiv.org": 3.0,    # arXiv API TOS 嚴格
    "arxiv.org": 5.0,
    # blog / RSS 站：預設 10 RPM
}

class DomainRateLimiter:
    def acquire(self, domain: str) -> None:
        # blocking：等到 token 可用才返回
        # token bucket：capacity=1，refill_rate=RPM/60 per second
        ...
```

設計要點：
- domain 自動從 URL 提取（`urllib.parse.urlparse(url).netloc`）
- 每個 domain 一個 lock + token bucket，互不影響
- 可從 `config/settings.py` 注入 per-domain override（env var `RATE_LIMIT_DOMAIN_XXX`）

#### 1-C：`infrastructure/http/retry.py`

**職責**：集中管理所有 HTTP 重試邏輯，取代現在各 scraper 分散的 try/except。

重試矩陣：

| 狀態碼 | 重試？ | 等待策略 |
|--------|--------|----------|
| 429 | ✅ 最多 4 次 | 優先讀 `Retry-After` header；沒有則 exponential (30s, 60s, 120s, 240s) |
| 503/502/504 | ✅ 最多 3 次 | exponential + jitter (5s, 15s, 45s) |
| 403 | ❌ 不重試 | 交由 `http_client` 換 UA 後再嘗試（最多 2 次） |
| 404/410 | ❌ | 直接失敗 |
| Timeout | ✅ 最多 3 次 | 固定 2s 間隔 |
| ConnectionError | ✅ 最多 3 次 | exponential + jitter |

```python
def make_retry_policy(
    max_attempts: int = 4,
    respect_retry_after: bool = True,
) -> tenacity.Retrying:
    ...
```

注意：`tenacity` 已在 `requirements.txt` 中，可直接用。

#### 1-D：`infrastructure/http/http_client.py`

**職責**：統一 HTTP GET，組合所有防護機制。

```python
class HttpClient:
    def __init__(
        self,
        rate_limiter: DomainRateLimiter,
        ua_pool: UserAgentPool,
        proxies: dict | None = None,
        max_403_rotations: int = 2,
    ): ...

    def get(self, url: str, timeout: int = 30, **kwargs) -> requests.Response:
        domain = _extract_domain(url)
        self._rate_limiter.acquire(domain)                    # 1. rate limit
        for attempt in range(self._max_403_rotations + 1):
            ua = self._ua_pool.get(domain)                    # 2. pick UA
            response = _retry_policy.call(                    # 3. retry on 429/5xx
                requests.get,
                url,
                headers={"User-Agent": ua, **kwargs.pop("headers", {})},
                proxies=self._proxies,
                timeout=timeout,
                **kwargs,
            )
            if response.status_code == 403:
                self._ua_pool.rotate(domain)                  # 4. 403 → 換 UA
                continue
            return response
        response.raise_for_status()                           # 超過 403 次數就拋

# Module-level singleton（Phase 1 快速接入用）
default_http_client: HttpClient = None  # 由 main.py 初始化後注入
```

**Phase 1 migration 步驟**（改動檔案清單）：

| 檔案 | 改動 |
|------|------|
| `scrapers/scrapers/rss_scraper.py` | `requests.get()` → `default_http_client.get()` |
| `scrapers/scrapers/blog_scraper.py` | 同上；robots.txt fetch 也改 |
| `scrapers/scrapers/arxiv_scraper.py` | 移除 ad-hoc retry loop → 改用 http_client |
| `scrapers/content_parsers/html_parser.py` | `fetch_and_parse()` 內改用 http_client |
| `main.py` 或 `__init__` | 初始化 `default_http_client` singleton |

Phase 1 完成後，`worker.py` 的 `time.sleep(5.0)` 可縮短到 0.5s（domain-level rate limit 已在 http_client 做了）。

---

### Phase 2 — Config 層分離（低風險，小 PR）

**目標**：`config.py` 不再做 DB 查詢。

#### 改動

`config/settings.py`
- 只讀環境變數（`DATABASE_URL`, `SENTRY_DSN`, per-domain rate limit 等）
- 不 import DB session，不 import SQLAlchemy models

`config/providers.py`
- 移入現在 `config.py:107-114` 的 `load_providers()`

DB 查詢（`get_sources()` / `get_sources_due()`）→ 移至：
- `infrastructure/persistence/sqlalchemy_repos/scraper_setting_repo_impl.py`

---

### Phase 3 — Ingestion Bounded Context

**目標**：建立 `ingestion/` 目錄，scrapers 改用 constructor injection 接受 `HttpClient`。

```
ingestion/
├── scrapers/
│   ├── base_scraper.py
│   ├── rss_scraper.py
│   ├── blog_scraper.py
│   └── arxiv_scraper.py
├── parsers/
│   ├── html_parser.py
│   └── pdf_parser.py
├── models/
│   └── scraped_article.py   # 原 scrapers/scrapers/article.py
└── services/
    └── scraper_service.py   # 統一 discover → dispatch 入口
```

重點改動：
- `arxiv_scraper.py` 的 DB keyword 查詢改為接受 `keyword_repo: ArxivKeywordRepository` 注入
- 所有 `__init__` 加入 `http_client: HttpClient` 參數
- `HtmlArticleParser` 改為接受 `http_client` 而非自己 `import requests`

---

### Phase 4 — Pipeline 層（純搬移）

```
pipeline/
├── dispatcher.py     # 原 scrapers/strategy/scrape_dispatcher.py
├── worker.py         # 原 scrapers/strategy/worker.py（delay 可縮短）
├── task.py           # 原 scrapers/strategy/scrape_task.py
├── queue_router.py
├── host_queue_map.py
└── queue_selector.py
```

無邏輯改動，只更新 import paths。

---

### Phase 5 — Domain 層（定義介面）

```
domain/
├── entities/
│   ├── article.py        # pure dataclass（不依賴 SQLAlchemy）
│   ├── analysis.py
│   └── failed_task.py
├── value_objects/
│   ├── url.py            # UrlHash，驗證邏輯
│   └── content.py
├── services/
│   └── dedup_service.py  # 從 main.py process_article() 抽出的 url_hash check
└── repositories/         # ABC only，不含實作
    ├── article_repository.py
    ├── analysis_repository.py
    └── scraper_setting_repository.py
```

注意：現有的 SQLAlchemy `models/` 資料夾保留不動。domain entities 是純 dataclass，用於 use case 間傳遞。persistence 層負責兩者之間轉換。

---

### Phase 6 — Application Layer（Use Cases）

**目標**：把 `main.py` 的業務邏輯拆成三個薄薄的 use case。

```python
# app/use_cases/run_scraper.py
class RunScraperUseCase:
    def __init__(
        self,
        scraper_setting_repo: ScraperSettingRepository,
        scraper_service: ScraperService,
        process_article_uc: ProcessArticleUseCase,
    ): ...
    def execute(self, correlation_id: str) -> RunSummary: ...

# app/use_cases/process_article.py
class ProcessArticleUseCase:
    def __init__(
        self,
        article_repo: ArticleRepository,
        dedup_service: DedupService,
        analyze_article_uc: AnalyzeArticleUseCase,
    ): ...
    def execute(self, scraped: ScrapedArticle, correlation_id: str) -> bool: ...

# app/use_cases/analyze_article.py
class AnalyzeArticleUseCase:
    def __init__(self, analyzer, analysis_repo: AnalysisRepository): ...
    def execute(self, article, prompt: str, correlation_id: str) -> bool: ...
```

---

### Phase 7 — Infrastructure Persistence（實作 Repository）

```
infrastructure/persistence/
├── db.py                                     # 原 src/database.py
└── sqlalchemy_repos/
    ├── article_repo_impl.py                  # implements ArticleRepository
    ├── analysis_repo_impl.py                 # implements AnalysisRepository
    └── scraper_setting_repo_impl.py          # 承接 config.py 的 get_sources_due()
```

---

### Phase 8 — Analysis Bounded Context（純搬移）

```
analysis/
├── services/analyzer_service.py     # 原 analyzers/provider_chain.py
├── providers/
│   ├── base.py
│   ├── gemini.py
│   └── openrouter.py
└── strategies/
    ├── leaky_bucket.py
    └── no_op.py
```

---

### Phase 9 — 瘦化 Entry Point

```python
# interfaces/cli/main.py（目標 < 40 行）
def main():
    configure_logging()
    init_db()

    http_client = HttpClient(
        rate_limiter=DomainRateLimiter(),
        ua_pool=UserAgentPool(),
        proxies=get_proxies(),
    )
    analyzer    = build_analyzer()
    session_factory = get_session

    use_case = RunScraperUseCase(
        scraper_setting_repo=ScraperSettingRepoImpl(session_factory),
        scraper_service=ScraperService(http_client),
        process_article_uc=ProcessArticleUseCase(
            article_repo=ArticleRepoImpl(session_factory),
            dedup_service=DedupService(),
            analyze_article_uc=AnalyzeArticleUseCase(
                analyzer=analyzer,
                analysis_repo=AnalysisRepoImpl(session_factory),
            ),
        ),
    )

    correlation_id = str(uuid.uuid4())
    use_case.execute(correlation_id)
```

---

## 執行順序與依賴關係

```
Phase 1 (HTTP infra)  ─── 可立即獨立上線，直接改善 429/403
    │
Phase 2 (Config)      ─── 小型 PR，低風險，可與 Phase 1 並行
    │
Phase 3 (Ingestion)   ─── 依賴 Phase 1
Phase 4 (Pipeline)    ─── 純搬移，可與 Phase 3 並行
    │
Phase 5 (Domain)      ─── 定義介面，不改邏輯
    │
Phase 6 (App layer)   ─┬─ 依賴 Phase 5
Phase 7 (Persistence) ─┘
    │
Phase 8 (Analysis)    ─── 可任意時間做，純搬移
    │
Phase 9 (Entry point) ─── 最後整合
```

---

## 檔案對應表（現在 → 新位置）

| 現在位置 | 新位置 | 改動程度 |
|----------|--------|----------|
| `src/main.py` | `src/interfaces/cli/main.py` | 大幅瘦化 |
| `src/config.py` | `src/config/settings.py` + `src/config/providers.py` | DB 查詢移走 |
| `src/database.py` | `src/infrastructure/persistence/db.py` | 搬移 |
| `src/scrapers/scrapers/rss_scraper.py` | `src/ingestion/scrapers/rss_scraper.py` | 改用 http_client |
| `src/scrapers/scrapers/blog_scraper.py` | `src/ingestion/scrapers/blog_scraper.py` | 改用 http_client |
| `src/scrapers/scrapers/arxiv_scraper.py` | `src/ingestion/scrapers/arxiv_scraper.py` | 移除 ad-hoc retry |
| `src/scrapers/scrapers/article.py` | `src/ingestion/models/scraped_article.py` | 搬移 |
| `src/scrapers/content_parsers/html_parser.py` | `src/ingestion/parsers/html_parser.py` | 改用 http_client |
| `src/scrapers/content_parsers/pdf_parser.py` | `src/ingestion/parsers/pdf_parser.py` | 搬移 |
| `src/scrapers/strategy/scrape_dispatcher.py` | `src/pipeline/dispatcher.py` | 搬移 |
| `src/scrapers/strategy/worker.py` | `src/pipeline/worker.py` | delay 可縮短 |
| `src/scrapers/strategy/scrape_task.py` | `src/pipeline/task.py` | 搬移 |
| `src/scrapers/strategy/{host_queue_map,queue_router,queue_selector}.py` | `src/pipeline/` | 搬移 |
| `src/analyzers/provider_chain.py` | `src/analysis/services/analyzer_service.py` | 搬移 |
| `src/analyzers/providers/` | `src/analysis/providers/` | 搬移 |
| `src/analyzers/strategies/` | `src/analysis/strategies/` | 搬移 |
| `src/observability/` | `src/infrastructure/observability/` | 搬移 |
| `src/notifications/` | `src/notifications/` | 維持原位 |
| `src/utils/proxy.py` | `src/utils/proxy.py` | 保留，http_client 引用 |
| `src/utils/sanitizer.py` | `src/utils/sanitizer.py` | 保留 |
| *(新建)* | `src/infrastructure/http/` | Phase 1 核心 |
| *(新建)* | `src/domain/` | Phase 5 |
| *(新建)* | `src/app/` | Phase 6 |
| *(新建)* | `src/infrastructure/persistence/sqlalchemy_repos/` | Phase 7 |
