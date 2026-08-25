---
layout: home

hero:
  name: Article Analyzer
  text: Specification Documentation
  tagline: SDD artifacts — specs, plans, data models, and interface contracts for all 24 features
  actions:
    - theme: brand
      text: Speckit SDD Guide
      link: /guide/speckit
    - theme: alt
      text: Project Constitution
      link: /constitution
    - theme: alt
      text: Browse Specs
      link: /specs/001-article-collection/spec

features:
  - title: '001 · Article Collection'
    details: 'Feature specification for Article Collection'
    link: '/specs/001-article-collection/spec'
  - title: '002 · Article Processing'
    details: '描述 002-article-processing capability 的現有行為，包含 DedupService 和 ProcessScrapedArticleUseCase 的去重邏輯、文章儲存、事件發布等行為'
    link: '/specs/002-article-processing/spec'
  - title: '003 · LLM Analysis'
    details: 'LLM analysis capability — AnalyzeArticleUseCase + ResilientLLMService + SlidingWindowStrategy'
    link: '/specs/003-llm-analysis/spec'
  - title: '004 · Translation'
    details: 'Partially brownfield — existing analysis/tag/group translation described as-is; article title and content translation are new greenfield requirements.'
    link: '/specs/004-translation/spec'
  - title: '005 · Tag Management'
    details: 'Brownfield spec — describes existing behavior of the tag management capability as it currently stands.'
    link: '/specs/005-tag-management/spec'
  - title: '006 · Observability'
    details: 'Brownfield spec — describe existing observability behavior in present tense, covering OTel metrics/traces, structlog+Loki logging, Sentry error tracking, GeoIP resolution, request logging, Telegram notifications, and their graceful no-op fallback patterns.'
    link: '/specs/006-observability/spec'
  - title: '007 · Scheduler'
    details: 'The scheduling entry point and pipeline assembly capability. Covers the run-once CLI entry point with startup jitter, signal handling, hard timeout scaffolding, and observability teardown, as well as the dependency injection/composition root that wires the full scrape-to-notify pipeline.'
    link: '/specs/007-scheduler/spec'
  - title: '008 · Article Sharing'
    details: '把 article-id 放入 query parameter，讓 URL 可以直接導向特定文章；在 ArticleCard 上新增 share icon；share 出來的 link 導向一個獨立的 layout，只顯示被選定的 ArticleCard。'
    link: '/specs/008-article-sharing/spec'
  - title: '009 · Guest Mode'
    details: '在登入頁面新增訪客模式選項，讓使用者可以用 guest 假帳號/狀態做有限度的 demo；訪客能看到真實第一頁文章，但功能受限（無 settings、無翻頁、graph 僅第一頁資料）。'
    link: '/specs/009-guest-mode/spec'
  - title: '010 · Grafana Tracing Charts'
    details: 'Fix OTel tracing pipeline to actually export spans to Grafana Cloud Tempo; replace broken Grafana image/iframe embedding in the monitoring dashboard with a native chart visualization approach that queries Grafana Cloud datasource APIs directly and renders charts client-side.'
    link: '/specs/010-grafana-tracing-charts/spec'
  - title: '011 · Semantic Scholar Scraper'
    details: '新增 Semantic Scholar scraper 至 scraping pipeline，以解決 arXiv rate limit 問題，同時擴大論文來源涵蓋範圍。實作後發現 Semantic Scholar 免費 API 無法個人申請 key，且首次執行即 429；改以 OpenAlex 作為主要免費學術論文 API 並同步實作。'
    link: '/specs/011-semantic-scholar-scraper/spec'
  - title: '012 · Rag Chatbot Integration'
    details: '在現有 scrape-analyzer 系統中整合 RAG（檢索增強生成）功能，讓使用者能透過對話介面詢問與已爬取文章相關的問題，系統以語意搜尋配合智慧回答回應使用者。'
    link: '/specs/012-rag-chatbot-integration/spec'
  - title: '013 · Dark Mode Toggle'
    details: '在 NavBar 加一個切換 light / dark / auto mode 的 icon，點擊依序切換，icon 隨之改變。RAG 元件隨 theme 更新。'
    link: '/specs/013-dark-mode-toggle/spec'
  - title: '014 · Article Recommendation Weekly Report'
    details: 'Feature specification for Article Recommendation Weekly Report'
    link: '/specs/014-article-recommendation-weekly-report/spec'
  - title: '015 · Guest Tutorial Mode'
    details: '在 guest mode 時新增一個 tutorial mode，加上一個類似於 stepper 的東西，一步一步地告訴使用者如何操作。後續追加需求：教學呈現方式改為「灰色 overlay + 對目標元素挖空 highlight + 頁面導覽 + 貼齊元素的說明對話框」，並擴充為所有使用者在新功能上線時都能看到對應的功能導覽（feature spotlight），且已讀狀態需要持久化。'
    link: '/specs/015-guest-tutorial-mode/spec'
  - title: '016 · DB Schema Brushup'
    details: 'Database schema brush-up (GitHub issue #91): all public-schema tables (other than `auth` and `vectors`, which already have their own PostgreSQL schema) are currently unorganized under `public`. Reorganize them into use-case-based PostgreSQL schemas via Alembic migrations, following the pattern already used for `auth`/`vectors`. Also add an AST-based step to the existing docs pipeline (`.github/workflows/speckit-github-pages.yml`) that reads the SQLAlchemy models and renders a database schema diagram (tables, columns, FK relationships, schema grouping) as a new page in the VitePress site.'
    link: '/specs/016-db-schema-brushup/spec'
  - title: '017 · Exception Handling Guideline'
    details: 'Exception handling guideline for src/ and API status code management for backend/ (GitHub issue #41). src/ 目前的 exception handling 很混亂:任何 function 都可以自行決定要不要 raise exception,exception 型別也不一致,exception propagation 也沒有良好結構。backend/ API 目前幾乎沒有妥善管理 status code。src/shared/domain/exceptions.py 已有 domain-specific exception hierarchy(016-db-schema-brushup 完成),此 feature 應以此為基礎,補齊(1) exception 使用規範/準則,(2) backend API 的 status code 對應規範與盤點。'
    link: '/specs/017-exception-handling-guideline/spec'
  - title: '018 · Public API Auth'
    details: '為目前完全公開(無任何 auth 檢查)的 backend API endpoint 加上「任何有效 token 即可」的存取控制,防止外部 consumer 繞過前端直接打 API 拿到未受保護的資料。不做 RBAC,只做「有沒有合法 token」的檢查。讓 backend 也對訪客發一組輕量的 guest JWT,前端的 Guest Mode 與訪客瀏覽都改成先跟 backend 換一組 guest token,之後打其他公開端點時帶上這組 token。真實登入使用者(含 admin)用原本的 JWT,角色仍從 User.role 判斷,不受影響。'
    link: '/specs/018-public-api-auth/spec'
  - title: '019 · Cicd Data Migrations'
    details: 'Bring the existing scripts/data/versions data-migration framework (analogous to alembic for one-off/backfill data jobs, tracked in the data_migrations table added by alembic migration 18) up to CI/CD parity with alembic itself, since it is currently a manual-only tool (make data-migrate) never invoked by .github/workflows/ci.yml or release.yml. Decided during design discussion: (1) trigger points are exactly ci.yml''s migrate job (staging) and release.yml''s release job (production), immediately after the existing alembic upgrade step, deliberately excluding the three ephemeral-per-job test databases; (2) each migration script declares an explicit predecessor reference (like alembic''s down_revision) instead of relying on numeric filename ordering; (3) each migration script may declare a minimum required schema state, checked as a reachability precondition (not an exact-transition match) before execution, refused loudly if unmet, and not persisted anywhere; (4) a failing migration''s writes are fully rolled back, it is not recorded as executed, no later chained migration runs in that pass, and the pipeline step fails — without reversing an already-successful schema migration in the same run; (5) migrations requiring external API access are always skipped by automatic runs, identical to today''s default manual behavior; (6) no new environment toggle, no new CI job, no change to existing manual invocation. The historical arXiv-ID data-cleanup migration that motivated this work is explicitly out of scope — separate follow-on work built on top of this framework.'
    link: '/specs/019-cicd-data-migrations/spec'
  - title: '020 · Redis Caching Layer'
    details: '在 frontend/app 中改善 Web Vitals 效能指標，做法是為現有直接打 DB 的 read API 加上 Redis caching 層，並在每日排程的 scraper pipeline 完成後（以及 admin 後台寫入時）主動維護快取；同時為 refresh_metrics 與 backfill_rag 兩個 CLI entrypoint 加上完成通知'
    link: '/specs/020-redis-caching-layer/spec'
  - title: '021 · Ssr Public Pages'
    details: 'Redis caching (020) sped up backend query responses but did not improve LCP on `/` (home) and `/articles`, because both pages are client-only with zero server-rendered data fetching — the browser has to download/parse/execute the JS bundle, hydrate, then fire two sequential API requests (topics, then articles) before the first meaningful content appears. Convert these pages to Server Components so first-paint data is fetched server-side and shipped with the initial HTML, actually cashing in on the caching work done in 020.'
    link: '/specs/021-ssr-public-pages/spec'
  - title: '022 · Lighthouse Performance Check'
    details: '我希望能夠在 Makefile 跟 scripts/ 裡面加上一個使用 lighthouse CLI 來去做 performance check 的一個腳本，並且最後出具一份report。可能需要涵蓋說我要使用哪個url，用甚麼身分(應該是用 guest)登入，以及指定要測試那些 route。然後出來的 report 希望是以繁體中文彙整。且之後會希望可以把他做在 .github/workflows/ci.yml 或是其他的 action 裡面。'
    link: '/specs/022-lighthouse-performance-check/spec'
  - title: '023 · Article Search'
    details: '我想要新增一個新的功能，那就是搜尋功能。具體來說，是要在 frontend/app/articles/page.tsx 中新增一個 search bar，當使用者在這個 search bar 上面輸入文字時，還要能夠觸發 auto-complete。為此，主要需要新增的功能為：1. Redis 與 models/ 裡面需要新增一個 prefix tree（但其實不是只有 prefix，所以可能要包含所有的 occurrence）2. src/entrypoints/cli/main.py 中要新增一個 stage 是去更新那個 tree（re-construct 而不是 append/update 可能會比較簡單）3. backend/ 中要去實作 autocomplete 以及 search 的端點與服務，search 的話因為 alembic/versions/21_add_vectors_schema_and_article_chunks.py 裡面應該是已經有 sparse vector 可以做 keyword-based 的資料查詢，不確定有沒有需要額外引用新的 tech stack 如 opensearch 之類的。而且 autocomplete 對於 response time 非常地要求，所以可能會需要在 Redis 上面指定一個 database index 專門 for 這個 prefix node 的 key-value cache 的形式。4. frontend 的部分需要實作 debounce 以節制 autocomplete API 的輸出，至於 search 後的頁面是否要用一個新的 UI 可以再討論。'
    link: '/specs/023-article-search/spec'
  - title: '024 · Async Pipeline Refactor'
    details: 'Rewrite the collection pipeline''s downstream stages (scrape → analyze → translate → RAG ingestion) into a genuinely concurrent, async, event-driven architecture, replacing the current fully-synchronous per-article chain. Full asyncio preferred over ThreadPoolExecutor for architectural fidelity to event-driven design. Discover/fetch/dedup stay batched as today — only downstream-of-publish stages become concurrent per-article. The event dispatch mechanism should stay swappable to an external/durable implementation later without touching stage logic. Concurrent access to shared model rate-limit capacity and to the database must be handled safely. RAG ingestion should not block other articles'' processing. Includes a model-pool dispatch upgrade so concurrent requests spread across every registered, currently-available model instead of queuing behind a single model.'
    link: '/specs/024-async-pipeline-refactor/spec'
---
