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
        arxiv_metadata_repo=None,  # ArxivMetadataRepository | None
    ) -> None:
        self._article_repo = article_repo
        self._dedup = dedup_service
        self._analyze_uc = analyze_article_uc
        self._arxiv_meta_repo = arxiv_metadata_repo

    def execute(
        self,
        scraped: ScrapedArticle,
        prompt: str,
        correlation_id: str,
        summary=None,
    ) -> bool:
        try:
            return self._process(scraped, prompt, correlation_id, summary)
        except Exception as e:
            logger.error("process_article_failed", url=scraped.url, error=str(e))
            if summary:
                summary.record_failed(scraped.source)
            return False

    def _process(self, scraped: ScrapedArticle, prompt: str,
                 correlation_id: str, summary) -> bool:
        existing = self._dedup.find_existing(scraped.url)

        if existing:
            logger.info("article_duplicate", url=scraped.url)
            if summary:
                summary.record_duplicate(scraped.source)
            if self._dedup.needs_analysis(existing):
                if existing.source == "arxiv" and self._arxiv_meta_repo is not None:
                    stored = self._arxiv_meta_repo.find_by_article_id(existing.id)
                    if stored:
                        existing.metadata["sections"] = stored.sections
                return self._analyze_uc.execute(existing, prompt, correlation_id)
            return False

        url_hash = UrlHash.from_url(scraped.url).value
        topic_id = UUID(scraped.topic_id) if scraped.topic_id else None
        article = ArticleEntity(
            url=scraped.url,
            url_hash=url_hash,
            source=scraped.source,
            title=scraped.title,
            content=scraped.content,
            published_at=self._parse_date(scraped.published_at),
            correlation_id=UUID(correlation_id),
            metadata=scraped.metadata or {},
            topic_id=topic_id,
        )
        article = self._article_repo.save(article)

        if article.source == "arxiv" and self._arxiv_meta_repo is not None:
            self._save_arxiv_metadata(article)

        if summary:
            summary.record_new(scraped.source)

        logger.info("article_saved", url=scraped.url, article_id=str(article.id))

        effective_prompt = scraped.prompt_override or prompt
        return self._analyze_uc.execute(article, effective_prompt, correlation_id)

    def _save_arxiv_metadata(self, article: ArticleEntity) -> None:
        from src.domain.entities.arxiv_metadata import ArxivMetadataEntity
        meta = article.metadata or {}
        entity = ArxivMetadataEntity(
            article_id=article.id,
            arxiv_id=meta.get("arxiv_id"),
            authors=meta.get("authors") or [],
            pdf_available=bool(meta.get("pdf_available", False)),
            sections=meta.get("sections") or {},
        )
        try:
            self._arxiv_meta_repo.save(entity)
        except Exception as e:
            logger.warning("arxiv_metadata_save_failed",
                           article_id=str(article.id), error=str(e))

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
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
