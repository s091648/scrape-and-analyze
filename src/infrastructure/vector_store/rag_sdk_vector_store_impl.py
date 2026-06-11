from src.modules.articles.domain.services.vector_store_service import VectorStoreService
from src.shared.logging import get_logger

logger = get_logger(__name__)


class RagSdkVectorStoreService(VectorStoreService):
    def __init__(self, processor) -> None:
        self._processor = processor

    def ingest(self, article) -> None:
        self._processor.ingest(
            full_text=article.content,
            metadata={
                "article_id": str(article.id),
                "source_url": str(article.url),
            },
        )
        logger.info("article_vectorized", article_id=str(article.id))
