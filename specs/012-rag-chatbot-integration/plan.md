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

**Primary Dependencies**: FastAPI（chat router）、SQLAlchemy + pgvector（向量儲存）、Redis（rate limiting）、外部 RAG SDK（TBD）、外部 React chat component package（TBD，local source build）

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
├── research.md          ← Phase 0 研究結果（外部介面提案）
├── data-model.md        ← Phase 1 輸出（TBD）
├── contracts/           ← Phase 1 輸出（TBD）
│   ├── chat-api.md      ← POST /chat/query SSE 合約
│   └── rag-sdk.md       ← RAG SDK 介面合約（待 SDK 開發者確認）
└── tasks.md             ← Phase 2 輸出（/speckit-tasks 產生）
```

### Source Code Layout

```text
# Scraper Pipeline 擴充（src/）
src/
├── modules/
│   └── articles/
│       ├── domain/
│       │   ├── services/
│       │   │   └── vector_store_service.py     ← 新增 Domain Interface
│       │   └── events/
│       │       └── article_vectorized_event.py ← 新增 Domain Event（TBD 是否需要）
│       └── application/
│           └── use_cases/
│               └── vectorize_article_use_case.py  ← 新增（可選，視複雜度決定）
└── infrastructure/
    └── vector_store/
        ├── __init__.py
        └── rag_sdk_vector_store_impl.py        ← 新增 Infrastructure 實作

# Backend Chat Service（backend/）
backend/
├── routers/
│   └── chat.py                                 ← 新增 FastAPI router
├── services/
│   └── chat_service.py                         ← 業務邏輯（rate limit + RAG 呼叫）
└── tests/
    └── test_chat.py                            ← 新增單元測試

# Frontend（frontend/）
frontend/
├── components/
│   └── features/
│       └── rag/
│           ├── InlineQABarWrapper.tsx          ← 包裝外部 InlineQABar
│           ├── InlineQABarWrapper.stories.tsx  ← Storybook story（Constitution 要求）
│           ├── FloatingChatbotWrapper.tsx      ← 包裝外部 FloatingChatbot
│           └── FloatingChatbotWrapper.stories.tsx
├── lib/
│   └── chat-session.ts                        ← sessionId 管理工具
└── tests/
    ├── unit/
    │   └── rag/
    │       └── InlineQABarWrapper.test.tsx
    └── integration/
        └── chat-flow.spec.ts                  ← Playwright E2E

# 資料庫（models/ + alembic/）
models/
└── article_chunk.py                           ← 新增 SQLAlchemy ORM model（vectors schema）

alembic/versions/
└── 18_add_vectors_schema_and_article_chunks.py ← 新增 migration

# Docker / 設定
docker-compose.yml                             ← 新增 redis service（若尚未存在）
pyproject.toml                                 ← 新增 RAG SDK 依賴
frontend/package.json                          ← 新增 chat component 依賴（local path or npm）
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

1. **RAG SDK 方法名稱與簽章** — 見 `research.md` 第 2 節提案，需 SDK 開發者確認
2. **Embedding 向量維度** — 影響 `vector(N)` 的 N，需確認後才能跑 migration
3. **Frontend component 的 SSE 支援方式** — 是 `fetch` SSE 還是 `EventSource`？影響 proxy 設定
4. **Frontend component history 管理** — 元件自管還是外部注入？影響 wrapper 複雜度
5. **RAG SDK 是否需要 local path install** — 若 SDK 尚未發布 npm/PyPI，需設定 monorepo workspace 或 path dependency
6. **Redis 是否已在 Railway 專案中** — 需確認 Railway 環境變數（`REDIS_URL`）

---

## Implementation Phases（供 /speckit-tasks 參考）

### Phase A：基礎設施準備
- Alembic migration：建立 `vectors` schema + `article_chunks` table
- Docker compose：新增 redis service
- 環境變數：`REDIS_URL`、`RAG_SDK_DB_URL`（或複用現有 DB URL）

### Phase B：Scraper Pipeline 擴充（src/）
- 定義 `VectorStoreService` Domain Interface
- 實作 `RagSdkVectorStoreImpl`（包裝外部 SDK）
- 在 `bootstrap.py` 訂閱事件，接向量化 handler
- 向量化失敗需 try/except，不中斷現有 pipeline

### Phase C：Backend Chat Service（backend/）
- 新增 `chat.py` router（POST /chat/query SSE endpoint）
- 實作 Redis rate limiting（guest cookie + user_id 兩條路徑）
- 整合 RAG SDK 的 `rag_query()`
- 新增 `/chat/session/{id}/history` 與 DELETE endpoint

### Phase D：Frontend 整合（frontend/）
- 安裝/連結外部 npm package（local path build）
- 建立 `InlineQABarWrapper` 與 `FloatingChatbotWrapper`
- 在 root layout 加入 `FloatingChatbotWrapper`
- 在文章列表頁加入 `InlineQABarWrapper`
- 實作 `chat-session.ts`（sessionId 生成與持久化）

### Phase E：測試
- scraper unit tests（mock SDK）
- backend unit + integration tests（chat router + rate limiter）
- frontend unit tests（wrapper components）
- E2E：完整問答流程 + rate limiting 行為
