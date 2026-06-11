# Data Model: RAG 智慧問答整合

## Database Entities（新增）

### ArticleChunk（`vectors.article_chunks`）

**SQLAlchemy model**: `models/article_chunk.py`
**Schema**: `vectors`（獨立 schema，與現有 `public` 隔離）

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK, default `gen_random_uuid()` | |
| `article_id` | UUID | FK → `articles.id` ON DELETE CASCADE, NOT NULL | |
| `chunk_index` | INT | NOT NULL | 片段在文章中的順序索引（0-based） |
| `content` | TEXT | NOT NULL | 原始片段文字 |
| `embedding` | VECTOR(768) | nullable | pgvector 768 維向量，索引建在此欄 |
| `source_url` | TEXT | nullable | 冗餘存文章 URL，加速回答時的引用查詢 |
| `created_at` | TIMESTAMPTZ | default `now()` | |

**Unique constraint**: `UNIQUE(article_id, chunk_index)` — 保證冪等性，重複 `ingest` 同一篇文章不產生重複片段

**Index**: `CREATE INDEX ... USING ivfflat (embedding vector_cosine_ops)` — cosine similarity ANN 查詢加速

**Relationship**: `article_id → Article.id`（cascade delete：文章刪除時對應片段一併移除）

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

**持久化**: 以 JSON 序列化存入 `sessionStorage`（key: `rag_chat_messages`）。換頁後保留，關 tab 後清除。

### ChatSession（概念層，無獨立型別）

後端無狀態，不儲存 session。「Session」僅指 `sessionStorage` 的生命週期。完整對話歷史（`Message[]`）在每次請求時由前端完整傳送給後端。

---

## Schema Migration

**Alembic revision**: `18_add_vectors_schema_and_article_chunks`

```sql
-- upgrade
CREATE SCHEMA IF NOT EXISTS vectors;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE vectors.article_chunks (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  article_id  UUID        NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  chunk_index INT         NOT NULL,
  content     TEXT        NOT NULL,
  embedding   VECTOR(768),
  source_url  TEXT,
  created_at  TIMESTAMPTZ DEFAULT now(),
  UNIQUE(article_id, chunk_index)
);

CREATE INDEX ON vectors.article_chunks USING ivfflat (embedding vector_cosine_ops);

-- downgrade
DROP INDEX IF EXISTS vectors.article_chunks_embedding_idx;
DROP TABLE IF EXISTS vectors.article_chunks;
DROP SCHEMA IF EXISTS vectors;
```

---

## Domain Interface（新增）

### VectorStoreService（`src/modules/articles/domain/services/vector_store_service.py`）

寫入路徑 interface，只需 `ingest`，不含查詢方法（查詢由外部 Chat Service 負責）。

```python
from abc import ABC, abstractmethod
from src.modules.articles.domain.entities.article import Article

class VectorStoreService(ABC):
    @abstractmethod
    def ingest(self, article: Article) -> None: ...
```
