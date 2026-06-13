import asyncio

from src.modules.intelligence.domain.services.rag_ingestion_service import RagIngestionService
from src.shared.logging import get_logger

logger = get_logger(__name__)


class RagSdkIngestionService(RagIngestionService):
    def __init__(self, processor) -> None:
        self._processor = processor

    def ingest(self, article) -> None:
        asyncio.run(self._processor.ingest(
            full_text=article.content,
            metadata={
                "url": str(article.url),
                "title": article.title,
                "source": article.source,
            },
        ))
        logger.info("article_rag_ingested", article_id=str(article.id))
