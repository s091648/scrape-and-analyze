# Contract: RAG SDK（IngestProcessor）

**Package**: `chatbot_plugin_sdk`（開發期：submodule path install；上線：PyPI 套件）
**Used by**: `src/infrastructure/intelligence/vector_store/rag_sdk_ingestion_impl.py`
**Scope**: 寫入路徑（`ingest`）。查詢/檢索由外部 Chat Service 負責，本系統不呼叫 SDK 的查詢 API。

---

## Class

```python
from chatbot_plugin_sdk.processors.ingest import IngestProcessor
```

本系統只使用 `IngestProcessor`。`QueryingProcessor` 完全封裝在外部 Chat Service 內，不 expose 給本系統。

---

## `ingest()`

```python
async def ingest(
    self,
    full_text: str,
    articles_column_values: Dict[str, Any],
) -> None
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `full_text` | `str` | Yes | 文章全文（任意來源：PDF 解析後文字、HTML stripped text、RSS 純文字） |
| `articles_column_values` | `dict` | Yes | 文章 metadata，詳見下方 |

**`articles_column_values` 欄位**：

```python
articles_column_values = {
    "url": str(article.url),
    "title": article.title,
    "source": article.source,
    "public_article_id": str(article.id),
    "topic_id": str(article.topic_id) if article.topic_id else None,
}
```

**SDK 內部步驟**（不 expose，由 SDK 管理）：
1. `chunk` — 切割全文為語意片段
2. `embed` — 每片段生成 embedding 向量（768 維）
3. `save` — 寫入 `vectors.article_chunks`；`UNIQUE(article_id, chunk_index)` 保證冪等性

**Error behaviour**: 失敗時 raise exception。Caller（`RagIngestionHandler`）須包在 `try/except` 並 log，**不得 re-raise**，確保現有 pipeline 繼續執行。

**Async**: `ingest()` 是 coroutine，caller 透過 `asyncio.run()` 在同步 context 中呼叫。

---

## 本系統的使用方式

### Domain Interface

```python
# src/modules/intelligence/domain/services/rag_ingestion_service.py
from abc import ABC, abstractmethod

class RagIngestionService(ABC):
    @abstractmethod
    def ingest(self, article, full_text: str) -> None: ...
```

### Infrastructure Implementation

```python
# src/infrastructure/intelligence/vector_store/rag_sdk_ingestion_impl.py
import asyncio
from chatbot_plugin_sdk.processors.ingest import IngestProcessor
from src.modules.intelligence.domain.services.rag_ingestion_service import RagIngestionService

class RagSdkIngestionService(RagIngestionService):
    def __init__(self, processor: IngestProcessor) -> None:
        self._processor = processor

    def ingest(self, article, full_text: str) -> None:
        topic_id = getattr(article, 'topic_id', None)
        asyncio.run(self._processor.ingest(
            full_text=full_text,
            articles_column_values={
                "url": str(article.url),
                "title": article.title,
                "source": article.source,
                "public_article_id": str(article.id),
                "topic_id": str(topic_id) if topic_id else None,
            },
        ))
```

### Use Case（Bot Detection + Fallback）

```python
# src/modules/intelligence/application/use_cases/ingest_article_for_rag.py
class IngestArticleForRagUseCase:
    def execute(self, article, full_text: str = "") -> None:
        # 1. full_text が空なら article フィールドから組み立て
        # 2. bot detection ページ（"verify you're not a robot" 等）はスキップ
        # 3. rag_ingestion_service.ingest(article, full_text) を呼び出す
```

### RAG Ingestion Handler

```python
# src/modules/intelligence/application/event_handlers/rag_ingestion_handler.py
class RagIngestionHandler:
    def handle(self, event) -> None:
        with tracer.start_as_current_span("article.rag_ingest"):
            try:
                self._use_case.execute(event.article, full_text=event.full_text)
            except Exception:
                logger.exception("rag_ingest_failed", ...)
                self._event_bus.publish(RagIngestionFailedEvent(...))
                # 不 re-raise：pipeline 繼續
```

### Bootstrap 配置

```python
# src/bootstrap.py（片段）
from chatbot_plugin_sdk.processors.ingest import IngestProcessor
processor = IngestProcessor()
# （設定由 SDK 內部讀取環境變數）
rag_ingestion_service = RagSdkIngestionService(processor)
ingest_use_case = IngestArticleForRagUseCase(rag_ingestion_service)
rag_handler = RagIngestionHandler(ingest_use_case, event_bus)
event_bus.subscribe(ArticleProcessedEvent, rag_handler.handle)
```

---

## 安裝設定

### 開發期（submodule path install）

`pyproject.toml`:
```toml
[tool.uv.sources]
chatbot-plugin-sdk = { path = "../chatbot-plugin", editable = true }

[project.optional-dependencies]
scraper = [
  # ... 現有依賴 ...
  "chatbot-plugin-sdk",
]
```

### 上線（PyPI）

確認套件名稱後，移除 `[tool.uv.sources]` 中的 path override，改為正式套件版本號。

---

## 相關環境變數

| 變數 | 用途 |
|------|------|
| `EMBEDDING_MODEL_API` | Embedding model API endpoint |
| `VECTOR_DB_NAME` | pgvector DB 名稱 |
| `VECTOR_DB_USER` | pgvector DB user |
| `VECTOR_DB_PASSWORD` | pgvector DB password |
