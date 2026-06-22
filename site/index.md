---
layout: home

hero:
  name: Scrape Analyzer
  text: Specification Documentation
  tagline: SDD artifacts — specs, plans, data models, and interface contracts for all 13 features
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
---
