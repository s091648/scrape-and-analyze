from src.shared.domain.entities import Article
from src.shared.domain.repositories import ArticleRepository
from src.shared.application.ports import EventBus
from src.shared.application.events import ArticleProcessedEvent
from src.shared.logging import get_logger
from src.modules.collection.domain import DedupService, UrlHash
from src.modules.collection.application.events import ArticleScrapedEvent

logger = get_logger(__name__)


class ProcessScrapedArticleUseCase:
    """
    Receives an ArticleScrapedEvent from infrastructure, applies dedup,
    persists a new Article if needed, and publishes ArticleProcessedEvent
    for downstream contexts to consume.
    """

    def __init__(
        self,
        article_repo: ArticleRepository,
        dedup_service: DedupService,
        event_bus: EventBus,
    ) -> None:
        self._article_repo = article_repo
        self._dedup_service = dedup_service
        self._event_bus = event_bus

    def execute(self, event: ArticleScrapedEvent) -> bool:
        existing = self._dedup_service.find_existing(event.url)

        if existing is not None:
            if not self._dedup_service.needs_analysis(existing):
                logger.info("article_already_analyzed", url=event.url)
                return False
            logger.info("article_needs_analysis", article_id=str(existing.id))
            self._event_bus.publish(ArticleProcessedEvent(article=existing))
            return True

        article = self._build_article(event)

        try:
            saved = self._article_repo.save(article)
        except Exception as e:
            logger.error("article_save_failed", url=event.url, error=str(e))
            return False

        logger.info("article_saved", article_id=str(saved.id), url=event.url)
        self._event_bus.publish(ArticleProcessedEvent(article=saved))
        return True

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
        )
