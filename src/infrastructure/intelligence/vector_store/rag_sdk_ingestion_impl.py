from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chatbot_plugin_sdk.processors.ingest import IngestProcessor

from src.modules.intelligence.domain.services.rag_ingestion_service import RagIngestionService
from src.shared.logging import get_logger

logger = get_logger(__name__)


class RagSdkIngestionService(RagIngestionService):
    def __init__(self, processor: IngestProcessor) -> None:
        self._processor: IngestProcessor = processor

    def ingest(self, article, full_text: str) -> None:
        start = time.monotonic()
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
        duration = time.monotonic() - start
        logger.info(
            "article_rag_ingested",
            article_id=str(article.id),
            article_title=article.title,
            article_url=str(article.url),
            full_text_chars=len(full_text),
            duration_seconds=round(duration, 3),
        )


class AsyncRagSdkIngestionService:
    """024-async-pipeline-refactor: async sibling of RagSdkIngestionService
    (untouched — still used by the out-of-scope build_rag_backfill_pipeline()
    via the unmodified build_rag_ingestion_service()). Awaits
    IngestProcessor.ingest() directly — it is already async — instead of
    wrapping it in asyncio.run(), which would raise if called from inside an
    already-running event loop (exactly the context this now runs in)."""

    def __init__(self, processor: "IngestProcessor") -> None:
        self._processor: "IngestProcessor" = processor

    async def ingest(self, article, full_text: str) -> None:
        start = time.monotonic()
        topic_id = getattr(article, 'topic_id', None)
        await self._processor.ingest(
            full_text=full_text,
            articles_column_values={
                "url": str(article.url),
                "title": article.title,
                "source": article.source,
                "public_article_id": str(article.id),
                "topic_id": str(topic_id) if topic_id else None,
            },
        )
        duration = time.monotonic() - start
        logger.info(
            "article_rag_ingested",
            article_id=str(article.id),
            article_title=article.title,
            article_url=str(article.url),
            full_text_chars=len(full_text),
            duration_seconds=round(duration, 3),
        )
