# Design Validation Report: Digital Twins Scraper (Railway Cron Job Edition)

**Reviewer Role:** Cloud Architect & QA Lead  
**Target Document:** `changes/digital-twins-scraper/design.md` (Railway Cron Job Version)  
**Date:** 2026-01-28

本報告針對調整為 **Railway Cron Job + Monolithic Script** 架構的設計進行審查。
**總評：** 這次的架構調整非常精準且務實。透過切換至 Cron Job 與同步執行模式，成功解決了前一版的成本與資料一致性 Gating Issues。這是一個非常適合 Side Project 與 MVP 階段的 "Low-Maintenance" 架構。目前的設計已無重大 Gating Issues，僅需注意幾個執行面的細節與長期擴展性風險。

---

## 1. Gating Issues (Must Fix Before Implementation)

**目前未發現 Gating Issues。**  
系統邏輯簡單、成本極低、且透過 Transaction 原子性解決了 Dual-Write 問題。設計已通過驗收標準。

---

## 2. Non-Gating Risks (Address Plan Required)

### [R1] 單次執行時間過長 (Timeouts)
- **Principle Reference:** Point 8 (Capacity)
- **Location:** `D5 (Railway Cron Jobs)` & `R2 (同步執行的延遲)`
- **Issue:**
    - 設計中採用 **同步流程 (Sequential Processing)**。
    - 假設每天有 100 篇新文章，每篇 LLM 解析需 10 秒 (Claude Sonnet 處理長文可能更久)，加上爬蟲延遲與 Retry，總執行時間可能超過 **20-30 分鐘**。
    - **Risk:** Railway 或 Docker Runtime 可能會有 **Execution Timeout** 限制 (雖 Cron Job 較寬鬆，但長時間連線可能被中斷)。
- **Recommendation:**
    - **Batch Processing:** 建議在 `run_daily_scrape` 中加入 `batch_size` 限制 (e.g. 每次執行只處理前 50 篇)，或者設定 **Max Execution Time** (e.g. 程式執行超過 50 分鐘自動停止，等待下一次排程繼續處理)。
    - **Concurrency (Optional):** 在 Python script 內部使用 `ThreadPoolExecutor` (max_workers=3-5) 並發處理 "爬蟲+解析" 流程，可大幅縮短總時間，且不會像 Celery 那樣增加架構複雜度。

### [R2] 記憶體溢出 (OOM) 風險
- **Principle Reference:** Point 8 (Capacity)
- **Location:** `D3 (專案結構)`
- **Issue:**
    - 單體腳本在長時間運行下，若 Python 物件 (如巨大的 HTML string 或 SQLAlchemy session cache) 未被正確回收，可能會導致 OOM (Railway Hobby Plan 記憶體有限)。
- **Recommendation:**
    - 確保在迴圈處理每篇文章後，明確地 `del article_content` 或重置 SQLAlchemy Session (`db.session.remove()`)，避免記憶體洩漏累積。

---

## 3. Nitpicks (Suggestions for Optimization)

### [N1] 失敗重試的 "Dead Letter" 處理
- **Location:** `D6 (錯誤處理)`
- **Comment:** 
    - 設計中失敗會寫入 `failed_tasks` 表，並提供手動補救腳本。
    - **建議:** 在 `run_daily_scrape` 每次啟動時，可以先自動檢查並重試 `failed_tasks` 中 `failed_at` 在 24 小時內的任務 (Auto-Redrive)，減少人工介入的需求。

### [N2] 依賴管理與 Docker Layer Caching
- **Location:** `D10 (Railway 部署配置)`
- **Comment:** 
    - `COPY src/ ./src/` 在 `pip install` 之後，這是好的實踐。
    - 建議明確指定 `PYTHONUNBUFFERED=1` 環境變數在 Dockerfile 中，確保 Logs 能即時輸出到 Railway Console，方便除錯 Timeout 或卡住的問題。

---

**Summary:**
這是一個優秀的架構修正。從複雜的 Microservices/Celery 回歸到 **Monolithic Cron Job**，對於這個規模的專案來說是 **Right-Sizing** (恰到好處的設計)。它以極低的成本 ($<1/月) 達成了所有的功能需求，且大幅降低了維運負擔。請在實作時留意執行時間與記憶體管理即可。
