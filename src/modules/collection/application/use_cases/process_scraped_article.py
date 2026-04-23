from typing import Optional

from src.shared.domain.entities import Article
from src.shared.domain.repositories import ArticleRepository
from src.shared.application.ports import EventBus
from src.shared.application.events import ArticleProcessedEvent
from src.shared.logging import get_logger
from src.modules.collection.domain.entities import ArxivMetadata
from src.modules.collection.domain.repositories import ArxivMetadataRepository
from src.modules.collection.domain.services import DedupService
from src.modules.collection.domain.value_objects import UrlHash
from src.modules.collection.application.dtos import ScrapedArticleDTO

logger = get_logger(__name__)


class ProcessScrapedArticleUseCase:
    """
    Receives a ScrapedArticleDTO from infrastructure, applies dedup,
    persists a new Article (and ArxivMetadata when applicable), and publishes
    ArticleProcessedEvent for downstream contexts to consume.
    """

    def __init__(
        self,
        article_repo: ArticleRepository,
        dedup_service: DedupService,
        event_bus: EventBus,
        arxiv_metadata_repo: Optional[ArxivMetadataRepository] = None,
    ) -> None:
        self._article_repo = article_repo
        self._dedup_service = dedup_service
        self._event_bus = event_bus
        self._arxiv_metadata_repo = arxiv_metadata_repo

    def execute(self, dto: ScrapedArticleDTO) -> bool:
        existing = self._dedup_service.find_existing(dto.url)

        if existing is not None:
            if not self._dedup_service.needs_analysis(existing):
                logger.info("article_already_analyzed", url=dto.url)
                return False
            # Enrich existing arxiv article with stored sections before re-analysis
            if existing.source == "arxiv" and self._arxiv_metadata_repo is not None:
                stored = self._arxiv_metadata_repo.find_by_article_id(existing.id)
                if stored and stored.sections:
                    existing.metadata["sections"] = stored.sections
            logger.info("article_needs_analysis", article_id=str(existing.id))
            self._event_bus.publish(ArticleProcessedEvent(article=existing))
            return True

        article = self._build_article(dto)

        try:
            saved = self._article_repo.save(article)
        except Exception as e:
            logger.error("article_save_failed", url=dto.url, error=str(e))
            return False

        if saved.source == "arxiv":
            self._save_arxiv_metadata(saved, dto.metadata)

        logger.info("article_saved", article_id=str(saved.id), url=dto.url)
        self._event_bus.publish(ArticleProcessedEvent(article=saved))
        return True

    def _build_article(self, dto: ScrapedArticleDTO) -> Article:
        return Article(
            url=dto.url,
            url_hash=UrlHash.from_url(dto.url).value,
            source=dto.source,
            title=dto.title,
            content=dto.content,
            published_at=dto.published_at,
            topic_id=dto.topic_id,
            metadata=dto.metadata,
        )

    def _save_arxiv_metadata(self, article: Article, metadata: dict) -> None:
        if self._arxiv_metadata_repo is None:
            return
        entity = ArxivMetadata(
            article_id=article.id,
            arxiv_id=metadata.get("arxiv_id"),
            authors=metadata.get("authors") or [],
            pdf_available=bool(metadata.get("pdf_available", False)),
            sections=metadata.get("sections") or {},
        )
        try:
            self._arxiv_metadata_repo.save(entity)
        except Exception as e:
            logger.warning("arxiv_metadata_save_failed",
                           article_id=str(article.id), error=str(e))