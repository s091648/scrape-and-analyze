# Implementation Plan: RAG 智慧問答整合

**Branch**: `012-rag-chatbot-integration` | **Date**: 2026-06-10 | **Spec**: [spec.md](./spec.md)

**Input**: 在現有 scraper-analyzer monorepo 中整合外部 RAG SDK（Python）與前端 Chat Component（React npm package），實現文章向量化 pipeline 擴充與使用者問答介面。

---

## Summary

將現有 scraper pipeline 擴充為：文章全文取得後，透過外部 RAG SDK 切 chunk、生成 embedding 並存入 pgvector。前端引入外部 npm package 的兩個元件（InlineQABar、FloatingChatbot），透過現有 Next.js proxy 連接新增的 FastAPI chat router，後端呼叫 RAG SDK 進行語意檢索並串流回答。Rate limiting 用 Redis，guest 用持久 Cookie 識別。

**外部依賴狀態**: RAG SDK 介面與 npm package props 皆尚未最終確定，本 plan 以 proposal 介面設計，實作時需依實際確認結果調整。

---

## Technical Context

**Language/Version**: Python 3.11（後端/scraper）、TypeScript + React 19.x（前端）

**Primary Dependencies**: FastAPI（chat router）、SQLAlchemy + pgvector（向量儲存）、Redis（rate limiting）、外部 RAG SDK（`VectorizingProcessor.ingest()`）、`chatbot-plugin-ui` npm package（`ChatbotPlugin` + `AgentInput` + `useChat`）

**Storage**: PostgreSQL `vectors` schema（新建）+ Redis（已有 Railway 支援）

**Testing**: pytest（scraper/backend unit + integration）、Vitest（frontend unit）、Playwright（E2E）

**Target Platform**: Railway（production）、Docker compose（local）

**Performance Goals**: 問答首次回應 < 10 秒（p90）、向量化於 pipeline 完成後 5 分鐘內可查詢

**Constraints**: 向量化失敗不得中斷現有 pipeline；Rate limiting 需在服務重啟後仍保持（持久化到 Redis）

**Scale/Scope**: 初版；向量維度 1536（依 embedding model，TBD）

---

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| I. DDD 層次分離 | ✅ PASS | `VectorStoreService` 作 Domain Interface；`RagSdkVectorStoreService` 在 Infrastructure |
| II. Atomic Frontend | ✅ PASS | Chat wrapper 元件放在 `components/features/rag/`；需補 Storybook stories |
| III. Test Discipline | ✅ PASS | 需包含 unit + integration tests；向量化用 mock SDK 做 unit test |
| IV. Docker-First | ✅ PASS | Redis 加入 `docker-compose.yml`；pgvector 已在 stack 中 |
| V. CI-Only Deploy | ✅ PASS | 無影響 |
| VI. Observability | ✅ PASS | VectorizeHandler 和 ChatRouter 需加 OTel span；rate limiting 需記 structured log |
| VII. Code Style | ✅ PASS | 新 router 照現有慣例；wrapper 元件用 Shadcn/UI 最小化擴充 |
| VIII. UML Conventions | ✅ PASS | 新 Domain Event 命名結尾 `Event`；Handler 命名 `VectorizeHandler` |

---

## Project Structure

### Documentation (this feature)

```text
specs/012-rag-chatbot-integration/
├── plan.md              ← 本檔案
├── spec.md              ← 需求規格
├── research.md          ← Phase 0 研究結果（所有介面已確認）
├── data-model.md        ← Phase 1 輸出 ✅
├── contracts/           ← Phase 1 輸出 ✅
│   ├── chat-api.md      ← POST /chat/completions OpenAI-compatible 合約
│   └── rag-sdk.md       ← IngestProcessor.ingest() 介面合約（chatbot_plugin_sdk）
└── tasks.md             ← Phase 2 輸出（/speckit-tasks 產生）
```

### Source Code Layout

```text
# Scraper Pipeline 擴充（src/）
src/
├── modules/
│   └── intelligence/
│       ├── domain/
│       │   └── services/
│       │       └── rag_ingestion_service.py      ← Domain Interface（RagIngestionService ABC）
│       └── application/
│           ├── use_cases/
│           │   └── ingest_article_for_rag.py     ← IngestArticleForRagUseCase（bot detection + fallback 組裝）
│           ├── event_handlers/
│           │   └── rag_ingestion_handler.py      ← RagIngestionHandler（try/except, OTel span）
│           └── events/
│               └── rag_ingestion_failed.py       ← RagIngestionFailedEvent
└── infrastructure/
    └── intelligence/
        └── vector_store/
            ├── __init__.py
            └── rag_sdk_ingestion_impl.py         ← RagSdkIngestionService（包裝 IngestProcessor）

# Backend Chat Service（backend/）
backend/
├── routers/
│   └── chat.py                                   ← FastAPI router（POST /chat/completions、GET /chat/quota）
├── services/
│   └── chat_service.py                           ← Rate limit 檢查 + proxy 至外部 Chat Service
└── tests/
    ├── test_chat_service.py                      ← ChatService 單元測試（rate limit 邏輯）
    └── test_chat_router.py                       ← chat router 路由測試

# Frontend（frontend/）
frontend/
├── components/
│   └── features/
│       └── rag/
│           ├── InlineQABarWrapper.tsx            ← useChat + AgentInput + AnswerDisplay + quota display
│           ├── AnswerDisplay.tsx                 ← 顯示最新 assistant 回答（markdown）
│           ├── FloatingChatbotWrapper.tsx        ← useChat hook + localStorage 歷史 + customAdapter（sources）
│           └── FloatingChatbotPanel.tsx          ← 自作浮動 UI（markdown 渲染、sources 來源 chip、ArticleDetailDialog）
├── lib/
│   ├── chat-session.ts                          ← sessionStorage 存取工具（InlineQABar 用）
│   └── providers/
│       ├── chat-quota-provider.tsx              ← ChatQuotaContext（GET /chat/quota 輪詢）
│       └── guest-mode-provider.tsx              ← GuestModeContext（訪客模式切換）
└── tests/
    ├── unit/
    │   └── rag/
    │       ├── InlineQABarWrapper.test.tsx
    │       └── FloatingChatbotWrapper.test.tsx
    └── integration/
        └── chat-flow.spec.ts                    ← Playwright E2E

# 資料庫（models/ + alembic/）
models/
└── article_chunk.py                             ← SQLAlchemy ORM model（vectors schema，SDK 內部寫入）

alembic/versions/
└── 21_add_vectors_schema_and_article_chunks.py  ← migration

# Docker / 設定
docker-compose.yml                               ← redis service 已加入
pyproject.toml                                   ← chatbot_plugin_sdk path dependency
frontend/package.json                            ← @s091648/chatbot-plugin-ui
```

---

## Complexity Tracking

| Item | Why Needed | Simpler Alternative Rejected Because |
|------|------------|--------------------------------------|
| Redis for Rate Limiting | Guest RPD 需跨重啟持久化，且需 IP fallback | In-memory 重啟歸零；PostgreSQL 讀寫頻繁且不適合高頻 counter |
| 新 `vectors` schema | 邏輯隔離，不汙染現有表格 | 放在 public schema 會與現有 ORM 命名空間混雜 |
| SSE 串流 | 問答生成需要逐步輸出，UX 要求 | Polling 延遲高；WebSocket 目前不需雙向通訊 |

---

## Open Questions（實作前需確認）

1. ~~**RAG SDK Query API 簽章**~~ — 不適用
2. ~~**Embedding 向量維度**~~ — 已確認 768 維
3. ~~**Frontend component 的 SSE 支援方式**~~ — 已確認：`fetch` streaming + 內建 `openaiAdapter`
4. ~~**Frontend component history 管理**~~ — 已確認：`useChat` hook 管理；FloatingChatbot は `localStorage`（userId タグ）で跨セッション持久化、ログアウト時クリア
5. ~~**外部 Chat Service URL 與 API Key**~~ — 已確認使用 `CHAT_SERVICE_URL` 環境變數
6. ~~**`topic_id` 傳遞方式**~~ — 已確認：後端從 `X-Topic-Id` header 取值，注入 request body extra field `{ ..., "topic_id": "..." }` 轉發給 Chat Service
7. ~~**RAG SDK local path install**~~ — 已確認：開發期間用 path dependency（`pip install -e ../rag-sdk`），上線前改為正式 PyPI 套件
8. ~~**Redis 是否已在 Railway 專案中**~~ — 已確認：需新增；本地 `docker-compose.yml` 需加 `redis` service，Railway 需新增 Redis plugin 並設定 `REDIS_URL`

---

## Implementation Phases（供 /speckit-tasks 參考）

### Phase A：基礎設施準備
- Alembic migration：建立 `vectors` schema + `article_chunks` table
- Docker compose：新增 redis service
- 環境變數：`REDIS_URL`、`RAG_SDK_DB_URL`（或複用現有 DB URL）

### Phase B：Scraper Pipeline 擴充（src/）
- 定義 `RagIngestionService` Domain Interface（`src/modules/intelligence/domain/services/`）
- 實作 `RagSdkIngestionService`（`src/infrastructure/intelligence/vector_store/rag_sdk_ingestion_impl.py`），包裝 `chatbot_plugin_sdk.processors.ingest.IngestProcessor`
- 實作 `IngestArticleForRagUseCase`：bot detection 過濾、full_text 為空時從 article 欄位組裝 fallback
- 實作 `RagIngestionHandler`：呼叫 use case，失敗時 publish `RagIngestionFailedEvent`，不 re-raise
- 在 `bootstrap.py` 訂閱事件，handler 接 `ArticleProcessedEvent`，full_text 從 event 取得（in-memory 傳遞）

### Phase C：Backend Chat Service（backend/）
- `chat.py` router：`POST /chat/completions`（SSE streaming）、`GET /chat/quota`（配額查詢）
- 實作 Redis rate limiting（guest cookie `__rag_gid` + user_id + IP fallback，bypass for admin）
- `ChatService` 驗證 rate limit → 轉發 OpenAI-compatible request 至 `CHAT_SERVICE_URL`，原樣 pipe SSE 回前端
- 從 `X-Topic-Id` header 取得 topic，注入轉發 body 的 extra field `{ ..., "topic_id": "..." }`

### Phase D：Frontend 整合（frontend/）
- 安裝 `@s091648/chatbot-plugin-ui` npm package（submodule local build）
- 建立 `ChatQuotaProvider`（`chat-quota-provider.tsx`）與 `GuestModeProvider`（`guest-mode-provider.tsx`）
- 建立 `FloatingChatbotPanel.tsx`：自作浮動 Chat UI（markdown 渲染、sources 來源 chip 點擊開啟 `ArticleDetailDialog`、新對話按鈕）
- 建立 `FloatingChatbotWrapper`：`useChat` hook + `customAdapter`（解析 SSE sources 事件）、`localStorage`（userId 標記）歷史持久化；未認證且非訪客模式時隱藏
- 建立 `InlineQABarWrapper`：`useChat` hook + `AgentInput` + `AnswerDisplay` + quota 顯示
- 在 root layout 加入 `FloatingChatbotWrapper`
- 在文章列表頁加入 `InlineQABarWrapper`
- Auth token 從 NextAuth session 取得後注入 `useChat({ headers: { Authorization: ... } })`
- Topic ID 從 `TopicContext` 取得後注入 `useChat({ headers: { 'X-Topic-Id': ... } })`

### Phase E：測試
- scraper unit tests（mock SDK）
- backend unit + integration tests（chat router + rate limiter）
- frontend unit tests（wrapper components）
- E2E：完整問答流程 + rate limiting 行為
