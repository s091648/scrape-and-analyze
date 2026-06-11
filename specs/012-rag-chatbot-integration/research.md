# Research: RAG 智慧問答整合

**Date**: 2026-06-10
**Status**: Phase 0 完成，RAG SDK 介面已確認；Frontend component 介面待確認

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

### Query API（待確認）

查詢相關方法（`search`, `rag_query` 等）由 `QueryingProcessor` 提供，介面尚未最終確認。目前 plan 中以 proposal 設計，待 SDK 開發者補充。

### Data Types（Proposal，待確認）
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
| ~~RAG SDK 方法名稱與簽章~~ | ✅ 已確認 | SDK 開發者 |
| ~~Embedding 向量維度~~ | ✅ 已確認（768） | SDK 開發者 |
| RAG SDK Query API（search / rag_query） | 待確認 | SDK 開發者 |
| Frontend component 是否自管 history state | 待確認 | npm package 開發者 |
| Frontend component 是否支援 SSE | 待確認 | npm package 開發者 |
| Frontend component 的 auth header 傳遞方式 | 待確認 | npm package 開發者 |
