# Contract: RAG SDK（VectorizingProcessor）

**Package**: `rag_sdk`（開發期：path install；上線：PyPI 套件）
**Used by**: `src/infrastructure/vector_store/rag_sdk_vector_store_impl.py`
**Scope**: 寫入路徑（`ingest`）。查詢/檢索由外部 Chat Service 負責，本系統不呼叫 SDK 的查詢 API。

---

## Class Hierarchy

```
RagArticleProcessor  (base)
└── VectorizingProcessor
    ├── configure(dbname, user, password, embedding_model_api)
    └── ingest(full_text, normalization, metadata)
```

本系統只使用 `VectorizingProcessor`。`QueryingProcessor` 完全封裝在外部 Chat Service 內，不 expose 給本系統。

---

## `configure()`

```python
def configure(
    self,
    dbname: str,
    user: str,
    password: str,
    embedding_model_api: Optional[str] = None,
) -> None
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `dbname` | `str` | Yes | PostgreSQL database name（vector DB） |
| `user` | `str` | Yes | DB user |
| `password` | `str` | Yes | DB password |
| `embedding_model_api` | `str \| None` | Yes（ingest 前必須設定） | Embedding model API endpoint |

在 composition root（`src/bootstrap.py`）中於 startup 時呼叫一次。

---

## `ingest()`

```python
def ingest(
    self,
    full_text: str,
    normalization: Optional[Union[str, Callable]] = None,
    metadata: Dict[str, Any] = {},
) -> None
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `full_text` | `str` | Yes | 文章全文（任意來源：PDF 解析後文字、HTML stripped text、RSS 純文字） |
| `normalization` | `str \| Callable \| None` | No | 切 chunk 與文字清理策略；`None` 使用 SDK 預設行為 |
| `metadata` | `dict` | Yes | 至少含 `article_id`（str UUID）與 `source_url`（str） |

**metadata 最小要求**:
```python
metadata = {
    "article_id": str(article.id),   # str UUID
    "source_url": str(article.url),  # 文章原始 URL
}
```

**SDK 內部步驟**（不 expose，由 SDK 管理）:
1. `chunk` — 切割全文為語意片段
2. `embed` — 每片段呼叫 `embedding_model_api` 生成 768 維向量
3. `save` — 寫入 `vectors.article_chunks`；`UNIQUE(article_id, chunk_index)` 保證冪等性

**Error behaviour**: 失敗時 raise exception。Caller（`VectorizeHandler`）須包在 `try/except` 並 log，**不得 re-raise**，確保現有 pipeline 繼續執行。

---

## 本系統的使用方式

### Domain Interface

```python
# src/modules/articles/domain/services/vector_store_service.py
from abc import ABC, abstractmethod

class VectorStoreService(ABC):
    @abstractmethod
    def ingest(self, article: Article) -> None: ...
```

### Infrastructure Implementation

```python
# src/infrastructure/vector_store/rag_sdk_vector_store_impl.py
from rag_sdk import VectorizingProcessor
from src.modules.articles.domain.services.vector_store_service import VectorStoreService

class RagSdkVectorStoreService(VectorStoreService):
    def __init__(self, processor: VectorizingProcessor) -> None:
        self._processor = processor

    def ingest(self, article: Article) -> None:
        self._processor.ingest(
            full_text=article.full_text,
            metadata={
                "article_id": str(article.id),
                "source_url": str(article.url),
            },
        )
```

### Vectorize Handler

```python
# src/infrastructure/vector_store/vectorize_handler.py
class VectorizeHandler:
    def __init__(self, vector_store: VectorStoreService) -> None:
        self._vector_store = vector_store

    def handle(self, event: AnalysisCompletedEvent) -> None:
        try:
            self._vector_store.ingest(event.article)
        except Exception:
            logger.exception("vectorize_failed", article_id=str(event.article.id))
            # 不 re-raise：pipeline 繼續
```

### Bootstrap 配置

```python
# src/bootstrap.py（片段）
processor = VectorizingProcessor()
processor.configure(
    dbname=settings.VECTOR_DB_NAME,
    user=settings.VECTOR_DB_USER,
    password=settings.VECTOR_DB_PASSWORD,
    embedding_model_api=settings.EMBEDDING_MODEL_API,
)
vector_store = RagSdkVectorStoreService(processor)
vectorize_handler = VectorizeHandler(vector_store)
event_bus.subscribe(AnalysisCompletedEvent, vectorize_handler.handle)
```

---

## 安裝設定

### 開發期（path install）

`pyproject.toml`:
```toml
[tool.uv.sources]
rag-sdk = { path = "../rag-sdk", editable = true }

[project.optional-dependencies]
scraper = [
  # ... 現有依賴 ...
  "rag-sdk",
]
```

### 上線（PyPI）

確認套件名稱後，移除 `[tool.uv.sources]` 中的 path override，改為正式套件版本號：
```toml
[project.optional-dependencies]
scraper = [
  # ... 現有依賴 ...
  "rag-sdk>=1.0.0",
]
```

---

## 相關環境變數

| 變數 | 用途 |
|------|------|
| `VECTOR_DB_NAME` | pgvector DB 名稱（通常與主 DB 相同） |
| `VECTOR_DB_USER` | pgvector DB user |
| `VECTOR_DB_PASSWORD` | pgvector DB password |
| `EMBEDDING_MODEL_API` | Embedding model API endpoint（`VectorizingProcessor.configure` 用） |
