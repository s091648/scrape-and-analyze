from typing import Optional

from src.shared.domain.entities import Article
from src.shared.domain.repositories import AsyncArticleRepository
from src.modules.collection.domain.services import AsyncDedupService
from src.modules.collection.domain.value_objects import UrlHash
from src.modules.collection.domain.repositories import AsyncArticleMetricsRepository
from src.modules.collection.application.events import ArticleScrapedEvent
from src.modules.collection.application.use_cases import ArticleOutcome
from src.shared.logging import get_logger

logger = get_logger(__name__)

# Opportunistic free-seed keys: metric values scrapers may already have parsed out
# of a provider's discover() response, forwarded to article_metric_values at zero
# extra cost. This is a best-effort optimization, not the metric catalog's source
# of truth — the authoritative refresh path (ResilientMetricsService, driven by the
# DB-configured metric_definitions catalog) is what keeps values current over time.
OPPORTUNISTIC_SEED_METRIC_KEYS = {"citation_count"}


class ProcessScrapedArticleUseCase:
    """
    Receives an ArticleScrapedEvent from infrastructure, applies dedup,
    persists a new Article.
    Returns (ArticleOutcome, Article | None) so the handler can publish events.

    024-async-pipeline-refactor: converted to async in place (`execute` is
    `async def`) — confirmed constructed only once, only inside
    build_collection_pipeline(), so no other caller needed a sync version
    preserved. Takes async repositories/services now.
    """

    def __init__(
        self,
        article_repo: AsyncArticleRepository,
        dedup_service: AsyncDedupService,
        article_metrics_repo: Optional[AsyncArticleMetricsRepository] = None,
    ) -> None:
        self._article_repo = article_repo
        self._dedup_service = dedup_service
        self._article_metrics_repo = article_metrics_repo

    async def execute(self, event: ArticleScrapedEvent) -> tuple[ArticleOutcome, Optional[Article]]:
        """Deduplicate and persist the scraped article, returning the outcome and saved Article (or None on failure/duplicate)."""
        existing = await self._dedup_service.find_existing(event.url)

        if existing is not None:
            if not await self._dedup_service.needs_analysis(existing):
                logger.info("article_already_analyzed", url=event.url)
                return ArticleOutcome.DUPLICATE, None
            logger.info("article_needs_analysis", article_id=str(existing.id))
            return ArticleOutcome.DUPLICATE_NEEDS_ANALYSIS, existing

        article = self._build_article(event)

        try:
            saved = await self._article_repo.save(article)
        except Exception as e:
            logger.error("article_save_failed", url=event.url, error=str(e))
            return ArticleOutcome.FAILED, None

        logger.info("article_saved", article_id=str(saved.id), url=event.url)

        if self._article_metrics_repo:
            try:
                # Always upsert (even with an empty dict) so every article gets an
                # article_metrics row for view_count tracking, matching prior behavior.
                metrics = {
                    key: event.metadata[key]
                    for key in OPPORTUNISTIC_SEED_METRIC_KEYS
                    if event.metadata.get(key) is not None
                }
                await self._article_metrics_repo.upsert(saved.id, metrics)
            except Exception as e:
                logger.warning("article_metrics_upsert_failed", article_id=str(saved.id), error=str(e))

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
