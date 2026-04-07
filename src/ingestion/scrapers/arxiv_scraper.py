from typing import List, Optional

from src.infrastructure.external.arxiv_client import ArxivClient, ArxivEntry
from src.ingestion.models.scraped_article import ScrapedArticle
from src.ingestion.scrapers.base_scraper import BaseScraper
from src.ingestion.parsers.pdf_parser import PdfParser
from src.pipeline.task import ScrapeTask
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ArxivScraper(BaseScraper):
    """
    Scraper for arXiv papers.

    Delegates HTTP + Atom parsing to ArxivClient (infrastructure).
    Domain decisions here: keyword query, date cutoff, PDF fetching.
    """

    def __init__(
        self,
        max_results: int = 100,
        days_back: int = 7,
        fetch_pdf: bool = True,
        client: ArxivClient = None,
    ) -> None:
        self.max_results = max_results
        self.days_back = days_back
        self.fetch_pdf = fetch_pdf
        self._client = client or ArxivClient()
        self._pdf_parser = PdfParser() if fetch_pdf else None

    # ── Public API ────────────────────────────────────────────────────────

    def discover(self) -> List[ScrapeTask]:
        from src.infrastructure.observability.otel_metrics import SCRAPER_ARTICLES_FOUND

        query = self._build_query()
        entries = self._client.fetch_entries(
            query=query,
            max_results=self.max_results,
            days_back=self.days_back,
        )
        tasks = [
            ScrapeTask(
                url=e.url,
                source="arxiv",
                metadata={"arxiv_id": e.arxiv_id},
                _execute_fn=lambda entry=e: self._build_article(entry),
            )
            for e in entries
        ]
        SCRAPER_ARTICLES_FOUND.add(len(tasks), {"source": "arxiv"})
        logger.info("arxiv_discover_complete", task_count=len(tasks))
        return tasks

    # ── Private helpers ───────────────────────────────────────────────────

    def _build_query(self) -> str:
        """Return search query: DB keywords if available, else hardcoded fallback."""
        try:
            from src.database import get_session
            from models.arxiv_keyword import ArxivKeyword
            session = get_session()
            try:
                keywords = session.query(ArxivKeyword).all()
                if keywords:
                    return " OR ".join(kw.keyword for kw in keywords)
            finally:
                session.close()
        except Exception as e:
            logger.warning("arxiv_keywords_db_fetch_failed", error=str(e))
        return (
            'ti:"digital twin" OR ti:"digital twins"'
            ' OR abs:"digital twin" OR abs:"cyber-physical"'
        )

    def _build_article(self, entry: ArxivEntry) -> Optional[ScrapedArticle]:
        pdf_text: Optional[str] = None
        pdf_available = False

        if self.fetch_pdf and entry.pdf_url:
            full_text = self._pdf_parser.parse(entry.pdf_url)
            if full_text:
                pdf_text = full_text
                pdf_available = True

        return ScrapedArticle(
            url=entry.url,
            title=entry.title,
            # Abstract goes in content — clean text for web display.
            # Full PDF text lives in metadata["pdf_text"] for LLM analysis only.
            content=entry.abstract,
            published_at=entry.published,
            source="arxiv",
            metadata={
                "authors": entry.authors,
                "arxiv_id": entry.arxiv_id,
                "abstract": entry.abstract,
                "pdf_available": pdf_available,
                "pdf_text": pdf_text,
            },
        )
