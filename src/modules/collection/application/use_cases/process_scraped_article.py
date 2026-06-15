from typing import Optional

from src.shared.domain.entities import Article
from src.shared.domain.repositories import ArticleRepository
from src.modules.collection.domain.services import DedupService
from src.modules.collection.domain.value_objects import UrlHash
from src.modules.collection.application.events import ArticleScrapedEvent
from src.modules.collection.application.use_cases import ArticleOutcome
from src.shared.logging import get_logger

logger = get_logger(__name__)


class ProcessScrapedArticleUseCase:
    """
    Receives an ArticleScrapedEvent from infrastructure, applies dedup,
    persists a new Article.
    Returns (ArticleOutcome, Article | None) so the handler can publish events.
    """

    def __init__(
        self,
        article_repo: ArticleRepository,
        dedup_service: DedupService,
    ) -> None:
        self._article_repo = article_repo
        self._dedup_service = dedup_service

    def execute(self, event: ArticleScrapedEvent) -> tuple[ArticleOutcome, Optional[Article]]:
        """Deduplicate and persist the scraped article, returning the outcome and saved Article (or None on failure/duplicate)."""
        existing = self._dedup_service.find_existing(event.url)

        if existing is not None:
            if not self._dedup_service.needs_analysis(existing):
                logger.info("article_already_analyzed", url=event.url)
                return ArticleOutcome.DUPLICATE, None
            logger.info("article_needs_analysis", article_id=str(existing.id))
            return ArticleOutcome.DUPLICATE_NEEDS_ANALYSIS, existing

        article = self._build_article(event)

        try:
            saved = self._article_repo.save(article)
        except Exception as e:
            logger.error("article_save_failed", url=event.url, error=str(e))
            return ArticleOutcome.FAILED, None

        logger.info("article_saved", article_id=str(saved.id), url=event.url)
        return ArticleOutcome.NEW, saved

    def _build_article(self, event: ArticleScrapedEvent) -> Article:
        """Construct an Article entity from an ArticleScrapedEvent."""
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
