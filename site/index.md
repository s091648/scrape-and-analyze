---
layout: home

hero:
  name: Scrape Analyzer
  text: Specification Documentation
  tagline: SDD artifacts — specs, plans, data models, and interface contracts for all 7 features
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
  - title: 001 · Article Collection
    details: RSS, blog, and ArXiv scraper — discovery, deduplication, and fetch pipeline specs
    link: /specs/001-article-collection/spec
  - title: 002 · Article Processing
    details: Article deduplication, storage, and event-driven processing pipeline
    link: /specs/002-article-processing/spec
  - title: 003 · LLM Analysis
    details: Resilient LLM provider chain with sliding-window rate limiting and fallback
    link: /specs/003-llm-analysis/spec
  - title: 004 · Translation
    details: Multi-language translation pipeline with parallel-table storage
    link: /specs/004-translation/spec
  - title: 005 · Tag Management
    details: Tag normalization, group definitions, and backfill strategies
    link: /specs/005-tag-management/spec
  - title: 006 · Observability
    details: OpenTelemetry, Loki, Sentry, and GeoIP integration contracts
    link: /specs/006-observability/spec
  - title: 007 · Scheduler
    details: Cron-based scheduling, pipeline orchestration, and graceful shutdown
    link: /specs/007-scheduler/spec
---
