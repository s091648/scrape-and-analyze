# Research: RAG 智慧問答整合

**Date**: 2026-06-10
**Status**: Phase 0 完成，外部介面待 SDK/Package 開發者確認

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
  embedding   VECTOR(1536),   -- 維度依 embedding model 決定，預設 1536 (OpenAI/Gemini)
  source_url  TEXT,
  created_at  TIMESTAMPTZ DEFAULT now(),
  UNIQUE(article_id, chunk_index)  -- 保證冪等性
);
CREATE INDEX ON vectors.article_chunks USING ivfflat (embedding vector_cosine_ops);
```

---

## 2. Python RAG SDK 介面提案（待確認）

**Decision**: 提議以下介面，待 SDK 開發者確認

**Status**: PENDING — 需 SDK 開發者確認後更新此欄

### Configuration
```python
sdk.configure(
    db_url: str,           # PostgreSQL connection string
    embedding_model: str,  # 模型識別字串，例如 "text-embedding-3-small"
    collection: str = "article_chunks"  # 目標 table/collection 名稱
) -> None
```

### Ingestion API（向量寫入）
```python
# 低層 API（可拆開用）
sdk.chunk(text: str, metadata: dict, strategy: ChunkStrategy = None) -> List[Chunk]
sdk.embed(chunks: List[Chunk]) -> List[EmbeddedChunk]
sdk.save(chunks: List[EmbeddedChunk]) -> List[str]   # 回傳 chunk IDs，idempotent by (doc_id, chunk_index)

# 補充 API
sdk.delete(document_id: str) -> int   # 刪除某文章的所有 chunks，回傳刪除數量

# Convenience shortcut（最常用）
sdk.ingest(text: str, metadata: dict) -> List[str]   # = chunk + embed + save
```

**Note**: DB transaction（connect/commit/rollback）建議由 SDK 內部管理，不 expose 給呼叫方。若需要 batch 寫入，可考慮提供 `begin_batch()` / `commit_batch()` 進階 API，初版可不實作。

### Query API（向量查詢 + 回答生成）
```python
# 低層 API
sdk.search(
    query: str,
    top_k: int = 5,
    filter: dict = None   # 例如 {"topic_id": "xxx"} 縮小搜尋範圍
) -> List[SearchResult]

sdk.generate(
    query: str,
    context: List[SearchResult],
    history: List[Message] = None
) -> GenerateResponse

# Convenience shortcut（後端最常用）
sdk.rag_query(
    question: str,
    history: List[Message] = None,
    filter: dict = None
) -> RAGResponse   # = search + generate，包含 answer + sources
```

### Data Types（建議）
```python
@dataclass
class SearchResult:
    chunk_id: str
    article_id: str
    content: str
    source_url: str
    score: float   # cosine similarity

@dataclass
class RAGResponse:
    answer: str
    sources: List[SearchResult]
    usage: dict   # token 使用量
```

---

## 3. Frontend React Component 介面提案（待確認）

**Decision**: 以下為提議 props，待 npm package 開發者確認

**Status**: PENDING — 需前端 package 開發者確認後更新此欄

### 共用基礎 Props
```typescript
interface ChatConfig {
  apiUrl: string;            // 後端 chat endpoint 的完整 URL
  sessionId: string;         // 由父元件管理（建議用 crypto.randomUUID()）
  authToken?: string | null; // JWT token，guest 傳 null
  topicId?: string | null;   // 縮小 RAG 搜尋範圍到特定 topic
  lang?: string;             // 顯示語言，預設跟隨 I18nProvider
}
```

### InlineQABar（內嵌問答欄）
```typescript
interface InlineQABarProps extends ChatConfig {
  placeholder?: string;
  onAnswer?(msg: ChatMessage): void;
  onError?(err: Error): void;
}
```

### FloatingChatbot（右下角浮動聊天）
```typescript
interface FloatingChatbotProps extends ChatConfig {
  initialOpen?: boolean;
  theme?: 'light' | 'dark';
  position?: 'bottom-right' | 'bottom-left';
  onOpen?(): void;
  onClose?(): void;
}
```

### 對話歷史管理
建議由元件自己管理 session state（不需外部注入 messages）。
父元件只需提供 `sessionId`，元件內部維護 `messages[]`。
若需要跨頁面保留歷史，元件可提供 `onHistoryChange` callback 讓父元件存到 localStorage。

---

## 4. 後端 Chat Service API 設計

**Decision**: 新增 FastAPI router，SSE 串流，Rate Limiting 用 Redis

### Endpoints
```
POST /chat/query
  Body: { question: str, session_id: str, history: list[Message], topic_id: str | None }
  Response: SSE stream

GET  /chat/session/{session_id}/history
  Response: { messages: list[Message] }

DELETE /chat/session/{session_id}
  Response: 204 No Content
```

### SSE Event Format
```json
{ "type": "delta",  "text": "部分回答文字" }
{ "type": "source", "url": "https://...", "title": "文章標題" }
{ "type": "done",   "usage": { "tokens": 1234 } }
{ "type": "error",  "message": "找不到相關資料" }
```

### SSE vs WebSocket 決策
**選擇 SSE，設計上保留升級路徑。**
- Tool Use / MCP 在 server-side 執行，結果透過 SSE 推送，client 不需雙向通訊
- SSE event format（`{type, payload}`）設計成與 WebSocket message 格式相容
- 如果未來需要 client-side tools（瀏覽器動作、使用者確認），屆時才換 WebSocket

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

## 未解決項目（待外部開發者確認）

| 項目 | 狀態 | 負責人 |
|------|------|-------|
| RAG SDK 方法名稱與簽章 | 待確認 | SDK 開發者 |
| Embedding 向量維度 | 待確認（影響 DB schema） | SDK 開發者 |
| Frontend component 是否自管 history state | 待確認 | npm package 開發者 |
| Frontend component 是否支援 SSE | 待確認 | npm package 開發者 |
| Frontend component 的 auth header 傳遞方式 | 待確認 | npm package 開發者 |
