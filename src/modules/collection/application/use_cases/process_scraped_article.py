from typing import Optional

from src.shared.domain.entities import Article
from src.shared.domain.repositories import ArticleRepository
from src.modules.collection.domain.entities import ArxivMetadata
from src.modules.collection.domain.repositories import ArxivMetadataRepository
from src.modules.collection.domain.services import DedupService
from src.modules.collection.domain.value_objects import UrlHash
from src.modules.collection.application.events import ArticleScrapedEvent
from src.modules.collection.application.use_cases import ArticleOutcome
from src.shared.logging import get_logger

logger = get_logger(__name__)


class ProcessScrapedArticleUseCase:
    """
    Receives an ArticleScrapedEvent from infrastructure, applies dedup,
    persists a new Article (and ArxivMetadata when applicable).
    Returns (ArticleOutcome, Article | None) so the handler can publish events.
    """

    def __init__(
        self,
        article_repo: ArticleRepository,
        dedup_service: DedupService,
        arxiv_metadata_repo: Optional[ArxivMetadataRepository] = None,
    ) -> None:
        self._article_repo = article_repo
        self._dedup_service = dedup_service
        self._arxiv_metadata_repo = arxiv_metadata_repo

    def execute(self, event: ArticleScrapedEvent) -> tuple[ArticleOutcome, Optional[Article]]:
        existing = self._dedup_service.find_existing(event.url)

        if existing is not None:
            if not self._dedup_service.needs_analysis(existing):
                logger.info("article_already_analyzed", url=event.url)
                return ArticleOutcome.DUPLICATE, None
            if existing.source == "arxiv" and self._arxiv_metadata_repo is not None:
                stored = self._arxiv_metadata_repo.find_by_article_id(existing.id)
                if stored and stored.sections:
                    existing.metadata["sections"] = stored.sections
            logger.info("article_needs_analysis", article_id=str(existing.id))
            return ArticleOutcome.DUPLICATE_NEEDS_ANALYSIS, existing

        article = self._build_article(event)

        try:
            saved = self._article_repo.save(article)
        except Exception as e:
            logger.error("article_save_failed", url=event.url, error=str(e))
            return ArticleOutcome.FAILED, None

        if saved.source == "arxiv":
            self._save_arxiv_metadata(saved, event.metadata)

        logger.info("article_saved", article_id=str(saved.id), url=event.url)
        return ArticleOutcome.NEW, saved

    def _build_article(self, event: ArticleScrapedEvent) -> Article:
        return Article(
            url=event.url,
            url_hash=UrlHash.from_url(event.url).value,
            source=event.source,
            title=event.title,
            content=event.content,
            published_at=event.published_at,
            topic_id=event.topic_id,
            metadata=event.metadata,
            original_source=event.metadata.get("original_source"),
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
