"""
ProcessArticleUseCase — deduplicate, persist, and trigger analysis for one article.

Extracted from main.py:process_article() + process_article_safe().
Depends only on domain interfaces; no ORM, no session management.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.app.use_cases.analyze_article import AnalyzeArticleUseCase
from src.domain.entities.article import ArticleEntity
from src.domain.repositories.article_repository import ArticleRepository
from src.domain.services.dedup_service import DedupService
from src.domain.value_objects.url import UrlHash
from src.ingestion.models.scraped_article import ScrapedArticle
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ProcessArticleUseCase:

    def __init__(
        self,
        article_repo: ArticleRepository,
        dedup_service: DedupService,
        analyze_article_uc: AnalyzeArticleUseCase,
    ) -> None:
        self._article_repo = article_repo
        self._dedup = dedup_service
        self._analyze_uc = analyze_article_uc

    def execute(
        self,
        scraped: ScrapedArticle,
        prompt: str,
        correlation_id: str,
        summary=None,
    ) -> bool:
        """
        Process a single scraped article:
          1. Check for duplicate URL.
          2. If new → save to store, then analyse.
          3. If duplicate but no analysis → analyse existing record.
          4. If duplicate with analysis → skip.

        Args:
            scraped:        DTO from the scraper.
            prompt:         LLM analysis prompt text.
            correlation_id: UUID string for the current run.
            summary:        Optional RunSummary for aggregated stats.

        Returns True if an analysis was produced, False otherwise.
        """
        try:
            return self._process(scraped, prompt, correlation_id, summary)
        except Exception as e:
            logger.error("process_article_failed", url=scraped.url, error=str(e))
            if summary:
                summary.record_failed(scraped.source)
            return False

    # ── private ───────────────────────────────────────────────────────────

    def _process(
        self,
        scraped: ScrapedArticle,
        prompt: str,
        correlation_id: str,
        summary,
    ) -> bool:
        existing = self._dedup.find_existing(scraped.url)

        if existing:
            logger.info("article_duplicate", url=scraped.url)
            if summary:
                summary.record_duplicate(scraped.source)
            if self._dedup.needs_analysis(existing):
                return self._analyze_uc.execute(existing, prompt, correlation_id)
            return False

        # New article
        url_hash = UrlHash.from_url(scraped.url).value
        article = ArticleEntity(
            url=scraped.url,
            url_hash=url_hash,
            source=scraped.source,
            title=scraped.title,
            content=scraped.content,
            published_at=self._parse_date(scraped.published_at),
            correlation_id=UUID(correlation_id),
            metadata=scraped.metadata or {},
        )
        article = self._article_repo.save(article)

        if summary:
            summary.record_new(scraped.source)

        logger.info("article_saved", url=scraped.url, article_id=str(article.id))
        return self._analyze_uc.execute(article, prompt, correlation_id)

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO or RFC-2822 date strings to datetime. Returns None on failure."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            pass
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            return None
