# Research: RAG 智慧問答整合

**Date**: 2026-06-10
**Status**: Phase 0 完成，所有介面已確認

---

## 1. 向量儲存方案

**Decision**: 使用現有 PostgreSQL + pgvector，新開 `vectors` schema

**Rationale**:
- pgvector image（`pgvector/pgvector:pg15`）已在 Docker stack 中，不需要新服務
- 新 schema（`vectors`）提供邏輯隔離，不汙染現有表格
- Alembic 可直接管理 schema 建立與 migration
- 後續若需要獨立向量 DB（效能需求大幅提升時），只需替換 Infrastructure 實作即可

**Alternatives considered**: Qdrant, Weaviate — 排除，因需額外 Docker service、額外維運成本，目前規模不需要

**Schema 設計**:
```sql
CREATE SCHEMA IF NOT EXISTS vectors;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE vectors.article_chunks (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  article_id  UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  chunk_index INT NOT NULL,
  content     TEXT NOT NULL,
  embedding   VECTOR(768),    -- 與 tag vector 維度一致，768 維
  source_url  TEXT,
  created_at  TIMESTAMPTZ DEFAULT now(),
  UNIQUE(article_id, chunk_index)  -- 保證冪等性
);
CREATE INDEX ON vectors.article_chunks USING ivfflat (embedding vector_cosine_ops);
```

---

## 2. Python RAG SDK 介面（已確認）

**Decision**: 使用外部 `RagArticleProcessor` 物件，已確認介面如下

**Status**: CONFIRMED

### Import
```python
from rag_sdk import RagArticleProcessor  # 套件名稱待定
```

### 類別設計：繼承架構

```
RagArticleProcessor (base)
├── configure(dbname, user, password)       # 僅設定 vector DB 連線
│
├── VectorizingProcessor (子類別)
│   └── configure(dbname, user, password, embedding_model_api)  # 額外設定 embedding model
│   └── ingest(full_text, normalization, metadata)              # 寫入流程：chunk → embed → save
│
└── QueryingProcessor (子類別)
    └── configure(dbname, user, password)    # 僅呼叫 super()，不需 embedding model
    └── search / rag_query 等查詢方法（待定）
```

### Method 1: `configure()`
```python
def configure(
    self,
    dbname: str,                        # Vector database 名稱
    user: str,                          # DB 使用者
    password: str,                      # DB 密碼
    embedding_model_api: Optional[str] = None  # Embedding model API endpoint
) -> None
```

- `dbname`, `user`, `password` 為 vector database 連線資訊
- `embedding_model_api` 為寫入時呼叫的 embedding model API；未設定則無法使用寫入功能
- **繼承設計**：
  - `VectorizingProcessor` 覆寫 `configure()`，加入 `embedding_model_api` 參數
  - `QueryingProcessor` 覆寫 `configure()`，僅呼叫 `super().configure(dbname, user, password)` 不需 embedding

### Method 2: `ingest()`
```python
def ingest(
    self,
    full_text: str,                                    # 文章全文
    normalization: Optional[Union[str, Callable]] = None,  # 正規化策略：字串名稱或 callable
    metadata: Dict[str, Any]                            # 文章 metadata（article_id, source_url 等）
) -> None
```

- 內部實作 `chunk`, `embed`, `commit/save` 三步驟，不 expose 這些私有方法
- `normalization` 可接受 callable 做客製化處理（例如自訂切 chunk 策略或文字清理）
- `metadata` 至少需包含 `article_id` 與 `source_url` 以支援引用來源

### Query API（不適用）

**本系統後端不直接呼叫 SDK 的 Query API。**

查詢（RAG 檢索 + 生成）由外部 Chat Service 負責，後端只需打一個 OpenAI-compatible 的 `/v1/chat/completions` endpoint，SDK 的 `QueryingProcessor` 完全封裝在該 Chat Service 內部，不 expose 給本系統。

因此 `VectorStoreService` Domain Interface 只需涵蓋**寫入路徑**（`ingest`），不需定義查詢相關方法。

---

## 3. Frontend React Component 介面（已確認）

**Decision**: package 原始碼已讀，介面確認如下

**Status**: CONFIRMED — 基於 `chatbot-plugin-ui` package 原始碼

### 元件清單

| 元件 | 用途 | 控制方式 |
|------|------|---------|
| `ChatbotPlugin` | 右下角浮動 FAB + 對話視窗 | Controlled（`messages`, `onSend`, `isLoading` 由父元件提供） |
| `AgentInput` | 內嵌搜尋輸入欄 + tool call cards | Controlled（`onSend`, `isLoading`；`messages` 只渲染 `role==='tool'` 的訊息） |
| `useChat` | 狀態管理 hook | 內建 `fetch` streaming，管理 `messages[]`，呼叫 `endpoint` |

### `useChat` hook（核心整合點）
```typescript
useChat({
  endpoint: '/api/proxy/chat/completions',  // Next.js proxy → backend
  streamAdapter: openaiAdapter,              // 預設，解析 OpenAI SSE 格式
  initialMessages: loadFromSessionStorage(), // 跨頁持久化
  headers: {
    'Authorization': `Bearer ${token}`,      // JWT 或省略（guest）
    'X-Topic-Id': topicId ?? '',             // 傳遞 topic filter
  },
})
```

### InlineQABarWrapper 顯示模式
`AgentInput` 只顯示 tool call messages，**assistant 回答不在元件內渲染**。
Wrapper 架構：
```tsx
// InlineQABarWrapper.tsx
const { messages, sendMessage, isLoading } = useChat({ ... })
const answer = messages.findLast(m => m.role === 'assistant')

return (
  <>
    <AgentInput onSend={sendMessage} isLoading={isLoading} messages={messages} />
    {answer && <AnswerDisplay message={answer} />}  {/* wrapper 自行渲染 */}
  </>
)
```

### 對話歷史持久化（sessionStorage）
```typescript
// chat-session.ts
const SESSION_KEY = 'rag_chat_messages'

export function loadSession(): Message[] {
  return JSON.parse(sessionStorage.getItem(SESSION_KEY) ?? '[]')
}
export function saveSession(messages: Message[]): void {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(messages))
}
export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY)
}
```
- 換頁保留，關 tab 消失
- `useChat` 的 `onMessage` callback 觸發 `saveSession()`

### Auth Header 傳遞
`useChat` 的 `headers` option 直接傳遞 `Authorization: Bearer {token}`，與現有 `apiFetch` 邏輯一致。

---

## 4. 後端 Chat Service API 設計

**Decision**: 後端作為薄 proxy，僅負責 Rate Limiting，不處理 RAG 邏輯；直接轉發 OpenAI-compatible stream

### 後端角色（精簡）

```
前端 → POST /api/proxy/chat/completions
     → Next.js proxy → backend POST /chat/completions
     → 後端驗證 rate limit → 轉發至 CHAT_SERVICE_URL/v1/chat/completions
     → streaming response 原樣回傳前端
```

- 後端**不轉換** stream 格式，直接 pipe OpenAI-compatible SSE 回前端
- RAG 檢索、引用來源生成、上下文管理全由外部 Chat Service 負責
- 引用來源以 markdown 格式嵌在回答文字中，不需自訂 SSE event

### 本後端對前端暴露的 Endpoint
```
POST /chat/completions
  Headers: Authorization: Bearer {jwt}  （guest 可省略）
           X-Topic-Id: {topic_id}        （optional，縮小 RAG 搜尋範圍）
  Body: OpenAI-compatible ChatCompletion request
    { "messages": [...], "stream": true }
  Response: OpenAI-compatible SSE stream（直接 pipe 自外部 Chat Service）
```

不需要 `GET /chat/session/{id}/history` 或 `DELETE` — 對話歷史由前端 `sessionStorage` 管理，後端無狀態。

### 外部 Chat Service 呼叫
```python
# 環境變數
CHAT_SERVICE_URL    # e.g. http://chat-service:8001
CHAT_SERVICE_API_KEY

# topic_id 從 X-Topic-Id header 取得，注入 request body extra field
body = { "messages": [...], "stream": True, "topic_id": topic_id }
POST {CHAT_SERVICE_URL}/v1/chat/completions
  Authorization: Bearer {CHAT_SERVICE_API_KEY}
  Body: body
```

### SSE 格式（OpenAI-compatible，直接 pass-through）
```
data: {"id":"...","choices":[{"delta":{"content":"部分回答"},"index":0}]}
data: {"id":"...","choices":[{"delta":{"content":""},"finish_reason":"stop"}]}
data: [DONE]
```

前端 `openaiAdapter`（package 內建）直接解析，不需客製。

---

## 5. Guest RPD 識別方案

**Decision**: 持久 Cookie `__rag_gid` + IP hash fallback

**Rationale**: session ID 會在 tab 切換/重新整理時重置，導致 RPD 計數被繞過

### 實作細節
```
Set-Cookie: __rag_gid=<UUID v4>; HttpOnly; SameSite=Lax; Max-Age=31536000; Path=/
```

- 後端在 guest 第一次呼叫時，在 response 中設置此 cookie
- Cookie 的 UUID 作為 Redis key 的一部分，不是 session ID
- **Redis key pattern**:
  - Guest:  `rate:guest:{cookie_uuid}:{YYYY-MM-DD}`
  - User:   `rate:user:{user_id}:{YYYY-MM-DD}`
  - Admin:  bypass（不寫 Redis）
- **TTL**: 86400 秒（每天午夜後自動重置）
- **Fallback**: 無 cookie（private browsing）→ `rate:guest:ip:{hash(IP+UA)}:{date}`

### 環境準備
- **本地**: `docker-compose.yml` 新增 `redis` service（`image: redis:7-alpine`），`backend` 與 `app` service 加入 `depends_on: redis`
- **Railway**: 新增 Redis plugin，`REDIS_URL` 環境變數由 Railway 自動注入
- **開發期 RAG SDK**: `pyproject.toml` 用 path dependency（`rag-sdk = { path = "../rag-sdk", editable = true }`），上線前替換為正式套件名稱

---

## 6. Pipeline 整合點

**Decision**: 在 `AnalyzeArticleUseCase` 完成後，由新的 `ArticleVectorizedEvent`（或現有 `AnalysisCompletedEvent`）觸發向量化

**Pipeline 修改點**:
1. 新增 Domain Event：`ArticleFullTextFetchedEvent`（若需要在分析前向量化）
   或複用 `AnalysisCompletedEvent`（若向量化在分析後執行）
2. 新增 `VectorizeHandler`（`src/infrastructure/vector_store/`）
3. 新增 Domain Interface：`VectorStoreService`（`src/modules/articles/domain/services/`）
4. 新增 Infrastructure 實作：`RagSdkVectorStoreService`（`src/infrastructure/vector_store/`）
5. 在 `src/bootstrap.py` 訂閱事件

**設計原則**: 向量化失敗不得中斷現有 pipeline，需包在 try/except 並記錄錯誤。

---

## 未解決項目

所有項目已確認，無待解決事項。

| 項目 | 狀態 | 結論 |
|------|------|------|
| ~~RAG SDK 方法名稱與簽章~~ | ✅ 已確認 | `VectorizingProcessor.ingest()` |
| ~~Embedding 向量維度~~ | ✅ 已確認 | 768 維 |
| ~~RAG SDK Query API~~ | ✅ 不適用 | 後端呼叫外部 Chat Service `/v1/chat/completions` |
| ~~Frontend component history state~~ | ✅ 已確認 | `useChat` hook 管理；wrapper 同步至 `sessionStorage` |
| ~~Frontend component SSE 支援~~ | ✅ 已確認 | `fetch` streaming + 內建 `openaiAdapter` |
| ~~Frontend component auth header~~ | ✅ 已確認 | `useChat({ headers: { Authorization: ... } })` |
| ~~CHAT_SERVICE_URL 環境變數~~ | ✅ 已確認 | 使用 `CHAT_SERVICE_URL` |
| ~~topic_id 傳遞方式~~ | ✅ 已確認 | request body extra field |
| ~~RAG SDK local path install~~ | ✅ 已確認 | 開發期 path dependency，上線改 PyPI |
| ~~Redis 是否已存在~~ | ✅ 已確認 | 需新增：本地 docker-compose + Railway plugin |
