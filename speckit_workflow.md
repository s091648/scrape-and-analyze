  用 Speckit 為 Brownfield 專案補 Spec

  Speckit 的標準流程（正向）

  speckit-specify → speckit-plan → speckit-tasks → speckit-implement
                                                           ↓
                                                 speckit-analyze（事後一致性檢查）

  Brownfield 的差異

  Spec 的寫法不變，但任務的性質改變：

  ┌───────────────────┬────────────────┬─────────────────────────────────────────┐
  │       階段        │   Greenfield   │               Brownfield                │
  ├───────────────────┼────────────────┼─────────────────────────────────────────┤
  │ spec.md           │ 描述想要的行為 │ 描述現有的行為（現在式）                │
  ├───────────────────┼────────────────┼─────────────────────────────────────────┤
  │ plan.md           │ 設計架構       │ 記錄既有架構決策                        │
  ├───────────────────┼────────────────┼─────────────────────────────────────────┤
  │ tasks.md          │ 實作任務       │ 驗證任務（補測試確認現有行為符合 spec） │
  ├───────────────────┼────────────────┼─────────────────────────────────────────┤
  │ speckit-implement │ 寫程式碼       │ 寫測試覆蓋現有邏輯                      │
  └───────────────────┴────────────────┴─────────────────────────────────────────┘

  ---
  組織方式：以 Capability 為單位，每個 Capability 一個 Feature Branch

  Speckit 的 check-prerequisites.sh 要求 branch 格式為 001-feature-name（數字前綴）。建議的分法：

  001-article-collection      ← scrapers (RSS/ArXiv/Blog) + ScrapeExecutor
  002-article-processing      ← DedupService + ProcessScrapedArticleUseCase
  003-llm-analysis            ← AnalyzeArticleUseCase + ResilientLLMService + SlidingWindowStrategy
  004-translation             ← TranslateArticleUseCase + TranslateTagsUseCase
  005-tag-management          ← NormalizeTags + TagGroupDefinition（最近才做的）
  006-observability           ← OTel + Loki + Telegram
  007-scheduler               ← entrypoints/cli/main.py + bootstrap.py

  不要按 pipeline stage 切（Discover/Fetch/Publish...），那是實作細節，spec 描述行為。

  ---
  src/infrastructure DDD 實作的處理原則

  ┌───────────────────────────────────────────┬────────────────────────────────────────────────────────┬────────────────────────────────────┐
  │                   元件                    │                     放在哪個 Spec                      │                原因                │
  ├───────────────────────────────────────────┼────────────────────────────────────────────────────────┼────────────────────────────────────┤
  │ Domain ABCs（LLMService, Scraper）        │ 同 capability 的 spec                                  │ 這是合約，屬於 capability 定義     │
  ├───────────────────────────────────────────┼────────────────────────────────────────────────────────┼────────────────────────────────────┤
  │ 純 repo impl（ArticleRepoImpl）           │ 不需要獨立 spec，在 capability spec 的 scenario 裡帶到 │ 是 how，不是 what                  │
  ├───────────────────────────────────────────┼────────────────────────────────────────────────────────┼────────────────────────────────────┤
  │ ResilientLLMService + rate limit          │ 003-llm-analysis                                       │ 有獨立的 WHEN/THEN 行為            │
  ├───────────────────────────────────────────┼────────────────────────────────────────────────────────┼────────────────────────────────────┤
  │ ScrapeExecutor（concurrency、robots.txt） │ 001-article-collection                                 │ 是 article-collection 能力的一部分 │
  └───────────────────────────────────────────┴────────────────────────────────────────────────────────┴────────────────────────────────────┘

  ---
  實際執行步驟

  # 1. 建立 feature branch（speckit 要求這個命名格式）
  git checkout -b 001-article-collection

  # 2. 跑 speckit-specify，描述現有行為
  # /speckit-specify 描述 RSS/ArXiv/Blog scraper 的現有行為、錯誤處理、rate limiting 等

  # 3. 審閱並跑 speckit-plan
  # /speckit-plan — 記錄既有架構：BaseScraper ABC, ScrapeExecutor, InMemoryEventBus

  # 4. 跑 speckit-tasks
  # /speckit-tasks — tasks 會是「寫測試確認 spec scenario 有對應覆蓋」為主

  # 5. 跑 speckit-implement
  # /speckit-implement — 補 unit/integration tests

  # 6. 可選：speckit-analyze 確認一致性
  # /speckit-analyze
