# Data Model: RAG 智慧問答整合

## Database Entities（新增）

兩張表均位於獨立的 `vectors` schema，與現有 `public` schema 隔離。

### VectorArticle（`vectors.articles`）

文章 metadata 的鏡像表，提供 chunk 查詢結果 join 所需的欄位，避免跨 schema FK 依賴。

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK | SDK 內部生成 |
| `url` | TEXT | NOT NULL, UNIQUE | 文章原始 URL |
| `title` | TEXT | nullable | 文章標題 |
| `source` | TEXT | nullable | 來源名稱（如 `arxiv`、`rss`） |
| `public_article_id` | UUID | nullable | 關聯回 `public.articles.id`（非 FK constraint） |
| `topic_id` | UUID | nullable | 關聯 `public.topics.id`（非 FK constraint） |
| `metadata` | JSONB | nullable | 額外 metadata |
| `created_at` | TIMESTAMPTZ | default `now()` | |
| `updated_at` | TIMESTAMPTZ | default `now()` | |

**Index**: `idx_articles_url`、`idx_articles_source`

---

### ArticleChunk（`vectors.article_chunks`）

#### DB Schema（migration `21_add_vectors_schema_and_article_chunks`）

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK, default `gen_random_uuid()` | |
| `article_id` | UUID | FK → `vectors.articles.id` ON DELETE CASCADE, NOT NULL | |
| `chunk_index` | INT | NOT NULL | 片段在文章中的順序索引（0-based） |
| `content` | TEXT | NOT NULL | 原始片段文字 |
| `dense_vector` | VECTOR(768) | nullable | Gemini embedding-001 dense 向量（768 維） |
| `sparse_vector` | SPARSEVEC(30522) | nullable | SPLADE sparse 向量（BERT vocab 30522 維） |
| `created_at` | TIMESTAMPTZ | default `now()` | |

**Unique constraint**: `UNIQUE(article_id, chunk_index)` — 保證冪等性，重複 `ingest` 同一篇文章不產生重複片段

**Index**:
- `USING hnsw (dense_vector vector_cosine_ops)` — dense cosine ANN 查詢加速
- `USING hnsw (sparse_vector sparsevec_cosine_ops)` — sparse cosine ANN 查詢加速

**Relationship**: `article_id → vectors.articles.id`（cascade delete：文章刪除時對應片段一併移除）

#### SQLAlchemy ORM Model（`models/article_chunk.py`）

> ⚠️ **實作偏差**: ORM model 欄位與 migration schema 不同——SDK 透過 migration schema 直接讀寫 DB；ORM model 為應用層補充定義，欄位如下：

| Python Column | DB Column | Type | Notes |
|---------------|-----------|------|-------|
| `id` | `id` | UUID | PK |
| `article_id` | `article_id` | UUID | FK → `articles.id`（`public` schema） |
| `chunk_index` | `chunk_index` | INT | |
| `content` | `content` | TEXT | |
| `embedding` | `dense_vector` | VECTOR(768) | 與 migration 欄位名稱不同 |
| `source_url` | —（不在 migration schema 中）| TEXT | nullable |
| `created_at` | `created_at` | TIMESTAMPTZ | |

---

## Client-Side Types（非 DB 持久化）

與 `chatbot-plugin-ui` npm package 的型別定義對齊（`src/types.ts`）。

### Message

| Field | Type | Notes |
|-------|------|-------|
| `id` | `string` (UUID) | `crypto.randomUUID()` 生成 |
| `role` | `'user' \| 'assistant' \| 'tool'` | |
| `content` | `string` | 文字內容（含 markdown 格式的引用來源） |
| `toolCall` | `ToolCall?` | 選填 |
| `toolResult` | `ToolCallResult?` | 選填 |
| `timestamp` | `Date` | |

**持久化策略**（依元件而異）：
- `FloatingChatbotWrapper`：以 JSON 序列化存入 `localStorage`（key: `rag_float_chat_messages`），附帶 `userId` 標記以防跨用戶洩漏；登出時自動清除。跨標籤頁持久，關閉瀏覽器後仍保留。
- `InlineQABarWrapper`：in-memory only，不持久化。
- `frontend/lib/chat-session.ts`：提供 `sessionStorage` 存取工具函式（`loadSession` / `saveSession` / `clearSession`，key: `rag_chat_messages`），備用。

### ChatSession（概念層，無獨立型別）

後端無狀態，不儲存 session。完整對話歷史（`Message[]`）在每次請求時由前端完整傳送給後端。

---

## Schema Migration

**Alembic revision**: `21_add_vectors_schema_and_article_chunks`

```sql
-- upgrade
CREATE SCHEMA IF NOT EXISTS vectors;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE vectors.articles (
  id                UUID        PRIMARY KEY,
  url               TEXT        NOT NULL UNIQUE,
  title             TEXT,
  source            TEXT,
  public_article_id UUID,
  topic_id          UUID,
  metadata          JSONB,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_articles_url    ON vectors.articles (url);
CREATE INDEX idx_articles_source ON vectors.articles (source);

CREATE TABLE vectors.article_chunks (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  article_id   UUID NOT NULL REFERENCES vectors.articles(id) ON DELETE CASCADE,
  chunk_index  INT  NOT NULL,
  content      TEXT NOT NULL,
  dense_vector VECTOR(768),
  sparse_vector SPARSEVEC(30522),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(article_id, chunk_index)
);
CREATE INDEX idx_article_chunks_dense_vector
  ON vectors.article_chunks USING hnsw (dense_vector vector_cosine_ops);
CREATE INDEX idx_article_chunks_sparse_vector
  ON vectors.article_chunks USING hnsw (sparse_vector sparsevec_cosine_ops);

-- downgrade
DROP TABLE IF EXISTS vectors.article_chunks CASCADE;
DROP TABLE IF EXISTS vectors.articles CASCADE;
DROP SCHEMA IF EXISTS vectors;
```

---

## Domain Interface（新增）

### RagIngestionService（`src/modules/intelligence/domain/services/rag_ingestion_service.py`）

寫入路徑 interface，只需 `ingest`，不含查詢方法（查詢由外部 Chat Service 負責）。

```python
from abc import ABC, abstractmethod

class RagIngestionService(ABC):
    @abstractmethod
    def ingest(self, article, full_text: str) -> None: ...
```

**實作**: `RagSdkIngestionService`（`src/infrastructure/intelligence/vector_store/rag_sdk_ingestion_impl.py`）包裝外部 `chatbot_plugin_sdk` 的 `IngestProcessor.ingest()`，傳入 `articles_column_values`（含 `public_article_id`、`url`、`title`、`source`、`topic_id`）。向量寫入由 SDK 直接操作 `vectors` schema，ORM model 僅供讀取查詢參考。
