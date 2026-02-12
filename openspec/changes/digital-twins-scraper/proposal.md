## Why

需要建立一個自動化的市場趨勢分析系統，透過定期爬蟲收集 Digital Twins（數位孿生）相關的技術文章、研究論文與產業動態，並利用 LLM 進行內容解析與洞見萃取，以支援市場分析決策。

## What Changes

- 新增 **每日爬蟲排程**：從科技新聞 RSS（TechCrunch、VentureBeat）、arXiv.org API、IoT World Today RSS 抓取 Digital Twins 相關內容
- 新增 **每週爬蟲排程**：從企業技術部落格（NVIDIA Blog、Siemens Digital Industries、AWS IoT Blog、Azure IoT Blog）抓取 Digital Twins 相關內容
- 新增 **原始資料儲存**：將爬蟲抓取的文章內容與 metadata 儲存至 PostgreSQL
- 新增 **LLM 內容解析**：透過 Claude API 解析文章本文，產生標籤（tags）、痛點、洞見、創新等摘要
- 新增 **解析結果儲存**：將 LLM 解析結果儲存至 PostgreSQL，並與原始資料建立關聯
- 新增 **任務佇列機制**：使用 Redis + Celery 處理爬蟲與 LLM 解析任務
- 新增 **錯誤處理機制**：實作 Celery 重試機制與失敗任務追蹤
- 新增 **IaC 配置**：使用 railway.toml 定義部署設定
- 新增 **可觀測性**：整合 Grafana Cloud 進行監控

## Capabilities

### New Capabilities

- `rss-scraper`: RSS 來源爬蟲功能，支援 TechCrunch、VentureBeat、IoT World Today 的每日排程爬蟲
- `api-scraper`: API 來源爬蟲功能，支援 arXiv.org API 的每日排程查詢
- `blog-scraper`: 企業部落格爬蟲功能，支援 NVIDIA、Siemens、AWS、Azure 部落格的每週排程爬蟲
- `content-storage`: 原始爬蟲內容與 metadata 的 PostgreSQL 儲存功能
- `llm-analyzer`: LLM 內容解析功能，支援標籤產生、痛點/洞見/創新摘要，並保持模型切換彈性
- `task-queue`: Celery + Redis 任務佇列，處理非同步爬蟲與 LLM 解析任務
- `scheduler`: Celery Beat 排程觸發機制（每日/每週）
- `observability`: Grafana Cloud 監控與告警整合

### Modified Capabilities

（無現有功能需要修改，這是全新專案）

## Impact

### 應用架構
- Database: PostgreSQL（Railway 託管）
- Cache/Queue: Redis（Railway 託管）
- Task Queue: Celery（Python）
- Scheduler: Celery Beat

### 部署配置
- Platform: Railway
- IaC: railway.toml + Git
- Container: Docker（Railway 自動處理）
- Orchestration: Railway 原生

### 外部依賴
- Claude API（Anthropic）- LLM 解析服務
- RSS Feeds: TechCrunch, VentureBeat, IoT World Today
- arXiv.org API
- 企業部落格: NVIDIA, Siemens, AWS IoT, Azure IoT

### 開發依賴
- Python: beautifulsoup4, requests, celery, redis, psycopg2, sqlalchemy
- Grafana Cloud（免費版）

### 可觀測性
- Grafana Cloud 免費版（metrics、logs、alerting）

### 成本考量
- Railway 資源用量（PostgreSQL、Redis、Worker instances）
- Claude API 呼叫次數
- Grafana Cloud 免費額度
