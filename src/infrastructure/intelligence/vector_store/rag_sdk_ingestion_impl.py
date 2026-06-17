import asyncio
import time

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
            metadata={
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
