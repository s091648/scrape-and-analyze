# Tasks: RAG 智慧問答整合

**Input**: `specs/012-rag-chatbot-integration/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: 每個 Phase 均包含測試任務（constitution §III 要求）

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可並行執行（不同檔案、無相依）
- **[Story]**: 對應 spec.md 中的 User Story（US1/US2/US3）

---

## Phase 1: Setup（基礎設施準備）

**Purpose**: 新增 Redis、環境變數、套件依賴，讓所有 User Story 的開發環境就緒

- [X] T001 在 `docker-compose.yml` 中新增 `redis` service（`image: redis:7-alpine`，port `6379:6379`），並在 `backend` 和 `app` service 的 `depends_on` 加入 `redis`
- [X] T002 [P] 在 `.env.example` 新增所有新增的環境變數：`REDIS_URL`, `CHAT_SERVICE_URL`, `CHAT_SERVICE_API_KEY`, `EMBEDDING_MODEL_API`, `VECTOR_DB_NAME`, `VECTOR_DB_USER`, `VECTOR_DB_PASSWORD`
- [X] T003 [P] 在 `pyproject.toml` 的 `scraper` dependency group 新增 RAG SDK path dependency（`[tool.uv.sources]` 區塊設定 `rag-sdk = { path = "../rag-sdk", editable = true }`）
- [X] T004 [P] 在 `frontend/package.json` 新增 `chatbot-plugin-ui` 套件依賴（local path 或 npm link），並在 frontend Docker container 中執行 `npm install`

**Checkpoint**: `docker compose up` 啟動無誤，redis service 正常運行

---

## Phase 2: Foundational（基礎層，阻擋所有 User Story 的前置作業）

**Purpose**: DB schema migration、ORM model、Domain Interface，所有 User Story 均依賴此 Phase

**⚠️ CRITICAL**: 所有 User Story 必須等此 Phase 完成後才能開始

- [X] T005 在 `alembic/versions/` 新增 migration `21_add_vectors_schema_and_article_chunks.py`，建立 `vectors` schema、啟用 `vector` extension、建立 `vectors.article_chunks` table（含 ivfflat index），down migration 完整實作（見 `data-model.md`）
- [X] T006 [P] 在 `models/article_chunk.py` 建立 `ArticleChunk` SQLAlchemy ORM model（schema=`vectors`，欄位：`id`, `article_id`, `chunk_index`, `content`, `embedding VECTOR(768)`, `source_url`, `created_at`，unique constraint `(article_id, chunk_index)`）
- [X] T007 [P] 在 `src/modules/articles/domain/services/vector_store_service.py` 建立 `VectorStoreService` ABC（單一抽象方法 `ingest(self, article: Article) -> None`）

**Checkpoint**: `make migrate` 執行成功，`vectors.article_chunks` table 存在於 DB

---

## Phase 3: US3 — 文章向量化（Pipeline 整合）（Priority: P1）

**Goal**: 文章完成分析後，自動向量化並存入 `vectors.article_chunks`，流程失敗不中斷現有 pipeline

**Independent Test**: 執行 `make scrape SOURCE=rss LIMIT=1`，完成後查詢 `SELECT COUNT(*) FROM vectors.article_chunks` 確認片段已寫入

### Tests for US3

- [X] T008 [P] [US3] 在 `src/tests/unit/test_vectorize_handler.py` 建立 `VectorizeHandler` 單元測試：mock `VectorStoreService`，驗證 `ArticleProcessedEvent` 觸發 `ingest()` 呼叫；驗證 `ingest()` 拋出例外時 handler 不 re-raise 且記錄 log
- [X] T009 [P] [US3] 在 `src/tests/unit/test_rag_sdk_vector_store_impl.py` 建立 `RagSdkVectorStoreService` 單元測試：mock `VectorizingProcessor`，驗證 `ingest()` 以正確 `full_text` 與 `metadata`（含 `article_id` 與 `source_url`）呼叫 SDK
- [X] T010 [US3] 在 `src/tests/integration/test_vectorization_pipeline.py` 建立 integration test（`@pytest.mark.integration`）：建立 test Article，觸發向量化 use case，驗證冪等性（重複呼叫不產生重複片段）

### Implementation for US3

- [X] T011 [US3] 在 `src/infrastructure/vector_store/__init__.py` 及 `src/infrastructure/vector_store/rag_sdk_vector_store_impl.py` 實作 `RagSdkVectorStoreService(VectorStoreService)`，包裝 `VectorizingProcessor.ingest()`（見 `contracts/rag-sdk.md`）
- [X] T012 [US3] 在 `src/infrastructure/vector_store/vectorize_handler.py` 實作 `VectorizeHandler`：`handle(self, event) -> None`，包 `try/except`，失敗時 `logger.exception(...)` 不 re-raise（符合 constitution §VIII Handler 命名規則）
- [X] T013 [US3] 在 `src/bootstrap.py` 中建立並配置 `VectorizingProcessor`（`configure()` 讀取環境變數）、建立 `RagSdkVectorStoreService`、建立 `VectorizeHandler`、`event_bus.subscribe(ArticleProcessedEvent, vectorize_handler.handle)`

**Checkpoint**: US3 可獨立驗證 — 執行 `make test`（unit）與 `make test-integration`（integration），向量化流程測試通過

---

## Phase 4: US1 — 文章問答（內嵌輸入欄）（Priority: P1）

**Goal**: 文章列表頁顯示 `InlineQABarWrapper`，使用者輸入問題後在下方看到回答（含 markdown 引用）

**Independent Test**: 瀏覽首頁，在 InlineQABar 輸入問題，確認系統回覆且回答以 markdown 格式呈現；驗證空白問題不送出請求

### Tests for US1

- [X] T014 [P] [US1] 在 `backend/tests/test_chat_service.py` 建立 `ChatService` 單元測試：mock Redis，驗證 guest/user/admin 三種身份的 rate limit 邏輯；驗證超過上限回傳 `RateLimitExceeded`；驗證首次 guest 請求時設置 `__rag_gid` cookie
- [X] T015 [P] [US1] 在 `backend/tests/test_chat_router.py` 建立 `POST /chat/completions` 路由測試：mock `ChatService`，驗證 200 SSE 回應、429 rate limit 回應、`X-Topic-Id` header 正確傳入 service
- [X] T016 [P] [US1] 在 `frontend/tests/unit/rag/InlineQABarWrapper.test.tsx` 建立 `InlineQABarWrapper` 單元測試（Vitest）：mock `useChat`，驗證 `AgentInput` 渲染、送出訊息後 `AnswerDisplay` 顯示 assistant 回答、空白輸入不觸發 `sendMessage`

### Implementation for US1

- [X] T017 [US1] 在 `backend/services/chat_service.py` 實作 `ChatService`：Redis rate limiting（guest cookie + user_id + IP fallback 三條路徑，admin bypass）、向外呼叫 `CHAT_SERVICE_URL/v1/chat/completions`（注入 `topic_id` extra field）、SSE response streaming（見 `contracts/chat-api.md`）
- [X] T018 [US1] 在 `backend/routers/chat.py` 實作 `POST /chat/completions` FastAPI router：解析 JWT（optional）取 identity tier、呼叫 `ChatService`、SSE `StreamingResponse`、429 exception handler、設置 `__rag_gid` cookie（guest 首次）
- [X] T019 [US1] 在 `backend/main.py` 引入並 `include_router` chat router（無 prefix）
- [X] T020 [P] [US1] 在 `frontend/lib/chat-session.ts` 實作 `loadSession()`, `saveSession(messages: Message[])`, `clearSession()`（使用 `sessionStorage`，key: `rag_chat_messages`）
- [X] T021 [P] [US1] 在 `frontend/components/features/rag/AnswerDisplay.tsx` 實作顯示最新 assistant 訊息的元件（`ReactMarkdown` 渲染 markdown，含錯誤狀態與 loading 狀態）
- [X] T022 [US1] 在 `frontend/components/features/rag/InlineQABarWrapper.tsx` 實作 wrapper：`useChat({ endpoint: '/api/proxy/chat/completions', streamAdapter: openaiAdapter, initialMessages: loadSession(), headers: { Auth, 'X-Topic-Id' } })`、渲染 `AgentInput` + `AnswerDisplay`、`onMessage` 時呼叫 `saveSession()`
- [X] T023 [P] [US1] 在 `frontend/stories/InlineQABarWrapper.stories.tsx` 新增 Storybook story（default + loading + withAnswer + error 四個 variant，constitution §II 要求）
- [X] T024 [US1] 在文章列表頁（`frontend/app/home-page-content.tsx`）加入 `<InlineQABarWrapper />`（登入用戶可見），從 `useSession` 取得 token、從 `TopicContext` 取得 `topicId`

**Checkpoint**: US1 可獨立驗證 — `make test` 後端測試通過；`npm run test` 前端測試通過；瀏覽首頁 InlineQABar 渲染正常

---

## Phase 5: US2 — 浮動聊天機器人（右下角 FAB）（Priority: P2）

**Goal**: 所有頁面右下角顯示 FAB，展開後可多輪對話，同 browser session 保留歷史

**Independent Test**: 任意頁面點擊右下角 FAB，展開對話視窗；進行至少 2 輪追問，確認系統能銜接上下文；關閉再開啟視窗，確認對話紀錄保留（同 tab）

### Tests for US2

- [X] T025 [P] [US2] 在 `frontend/tests/unit/rag/FloatingChatbotWrapper.test.tsx` 建立 `FloatingChatbotWrapper` 單元測試（Vitest）：mock `useChat`，驗證 FAB 點擊展開/關閉、多輪訊息顯示、`sessionStorage` 讀寫行為
- [ ] T026 [US2] 在 `frontend/tests/integration/chat-flow.spec.ts` 建立 Playwright E2E 測試：FAB 展開、輸入問題、驗證串流回答顯示；換頁後回來驗證對話紀錄保留；rate limit 達上限後驗證 429 提示訊息顯示（不崩潰）

### Implementation for US2

- [X] T027 [US2] 在 `frontend/components/features/rag/FloatingChatbotWrapper.tsx` 實作 wrapper：`useChat`（共用 `loadSession` / `saveSession`）、渲染 `ChatbotPlugin`（`messages`, `onSend`, `isLoading` props）、從 `useSession` 取 token、從 `TopicContext` 取 `topicId`、on error 顯示 toast 錯誤（不崩潰頁面）
- [X] T028 [P] [US2] 在 `frontend/stories/FloatingChatbotWrapper.stories.tsx` 新增 Storybook story（default + conversation + loading + error 四個 variant，constitution §II 要求）
- [X] T029 [US2] 在 `frontend/app/layout-shell.tsx` 加入 `<FloatingChatbotWrapper />`（ErrorBoundary 內側，session provider 可用）

**Checkpoint**: US2 可獨立驗證 — `npm run test` 前端測試通過；`npm run test:e2e` E2E 測試通過；瀏覽任意頁面 FAB 正常渲染

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Observability、錯誤處理補強，跨 User Story 的收尾

- [X] T030 [P] 在 `backend/routers/chat.py` 新增 OTel span（`chat.completions`），記錄 `identity_tier`、`rate_limit_remaining`、`topic_id`、Chat Service 回應狀態（constitution §VI）
- [X] T031 [P] 在 `src/infrastructure/vector_store/vectorize_handler.py` 新增 OTel span（`article.vectorize`），記錄 `article_id`、成功/失敗狀態（constitution §VI）
- [X] T032 [P] 在 `backend/services/chat_service.py` 補強 structured log：每次請求記錄 `identity_tier`、`rate_limit_counter`、`chat_service_status`（structlog，constitution §VI）
- [X] T033 在 `frontend/components/features/rag/InlineQABarWrapper.tsx` 與 `FloatingChatbotWrapper.tsx` 補強錯誤邊界：`useChat` 的 `onError` callback 顯示 user-friendly 提示（`503` → 「問答服務暫時無法使用」；`429` → 「已達每日上限」），確保不顯示技術錯誤訊息（spec SC-006）
- [X] T034 [P] 更新 `frontend/lib/providers/locales/en.json` 與 `zh-TW.json`，新增 `rag.*` i18n key（placeholder、error messages、empty state、assistantTitle）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 無依賴，立即開始
- **Foundational (Phase 2)**: 依賴 Phase 1 完成
- **US3 (Phase 3)**: 依賴 Phase 2 ─ 提供向量資料
- **US1 (Phase 4)**: 依賴 Phase 2 ─ 後端 chat endpoint；可與 US3 並行開發（backend/frontend 不需要 US3 的向量資料即可建置和測試）
- **US2 (Phase 5)**: 依賴 Phase 4（共用 `chat-session.ts`、`useChat` 設定模式）
- **Polish (Phase 6)**: 依賴所有 User Story 完成

### User Story Dependencies

- **US3 (P1)**: Phase 2 完成後可開始，不依賴其他 US
- **US1 (P1)**: Phase 2 完成後可開始，**可與 US3 並行**
- **US2 (P2)**: 依賴 US1（共用 `chat-session.ts`、`AnswerDisplay` 邏輯模式）

### Within Each User Story

- 測試任務先寫（確認失敗）→ 實作 → 確認測試通過
- Models/Domain → Services → Router → Frontend → Integration
- 每個 Checkpoint 都可獨立驗證該 Story

### Parallel Opportunities

- T008, T009 可並行（不同測試檔案）
- T011, T012 可在 T010（integration test 先寫確認失敗）後並行
- T014, T015, T016 可並行（測試檔案獨立）
- T017, T018 T017 先完成後 T018 依賴它
- T020, T021 可並行（不同 lib/component 檔案）
- T027, T028 可並行
- T030, T031, T032 可並行

---

## Parallel Example: US1（Phase 4）

```bash
# Step 1 — 並行寫測試（全部先確認 FAIL）:
Task T014: backend/tests/test_chat_service.py
Task T015: backend/tests/test_chat_router.py
Task T016: frontend/tests/unit/rag/InlineQABarWrapper.test.tsx

# Step 2 — 後端實作（T017 先，T018 依賴 T017）:
Task T017: backend/services/chat_service.py
Task T019: backend/main.py  ← 可與 T017 並行
→ Task T018: backend/routers/chat.py  ← T017 完成後

# Step 3 — 前端實作（並行）:
Task T020: frontend/lib/chat-session.ts
Task T021: frontend/components/features/rag/AnswerDisplay.tsx
→ Task T022: frontend/components/features/rag/InlineQABarWrapper.tsx  ← T020, T021 完成後
Task T023: frontend/components/features/rag/InlineQABarWrapper.stories.tsx

# Step 4 — 整合:
Task T024: frontend/app/page.tsx（接入頁面）
```

---

## Implementation Strategy

### MVP First（US3 + US1 Only）

1. 完成 Phase 1: Setup
2. 完成 Phase 2: Foundational（migrate、ORM model、domain interface）
3. 完成 Phase 3: US3（向量化 pipeline）
4. 完成 Phase 4: US1（InlineQABar）
5. **STOP & VALIDATE**: 端對端問答流程可用
6. 可上線驗收

### Incremental Delivery

1. Phase 1 + 2 → 基礎就緒
2. Phase 3 → 向量資料開始累積
3. Phase 4 → InlineQABar 可用（MVP！）
4. Phase 5 → 浮動聊天機器人可用
5. Phase 6 → 收尾

---

## Notes

- `[P]` = 不同檔案、無相依，可並行
- US3 與 US1 後端可並行開發（US1 chat endpoint 不依賴向量資料存在）
- E2E 測試（T026）需要 US3 向量資料才能完整驗證，建議在 US3 完成後執行
- `make migrate` 須在 `docker compose exec job_service` 中執行（constitution §IV）
- 所有 `npm install` 須在 frontend Docker container 中執行（memory：feedback_npm_install_docker）
