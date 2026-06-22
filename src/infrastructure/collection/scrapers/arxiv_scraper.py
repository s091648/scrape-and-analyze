from typing import List, Optional
from uuid import UUID

from src.shared.logging import get_logger
from src.infrastructure.collection.clients import ArxivClient, ArxivRateLimitedError
from .base_scraper import BaseScraper
from src.modules.collection.domain.entities import ScrapeJob
from src.modules.collection.domain.value_objects import ScrapedArticle
from src.infrastructure.collection.parsers import PdfParser

logger = get_logger(__name__)


class ArxivScraper(BaseScraper):
    """Discovers and fetches academic papers from the arXiv Export API."""

    def __init__(
        self,
        max_results: int = 100,
        days_back: int = 7,
        fetch_pdf: bool = True,
        keywords: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        topic_id: Optional[UUID] = None,
        prompt_override: Optional[str] = None,
        client: ArxivClient = None,
    ) -> None:
        self._max_results = max_results
        self._days_back = days_back
        self._fetch_pdf = fetch_pdf
        self._keywords = keywords
        self._categories = categories
        self._topic_id = topic_id
        self._prompt_override = prompt_override
        self._client = client or ArxivClient()  # fallback for standalone usage
        self._pdf_parser = PdfParser() if fetch_pdf else None

    def discover(self) -> List[ScrapeJob]:
        """Query the arXiv API and return ScrapeJobs for matching papers."""
        query = self._build_query()
        try:
            entries = self._client.fetch_entries(
                query=query,
                max_results=self._max_results,
                days_back=self._days_back,
            )
        except ArxivRateLimitedError as e:
            logger.warning("arxiv_rate_limited", message=str(e))
            raise
        jobs = []
        for e in entries:
            jobs.append(ScrapeJob(
                url=e.url,
                source="arxiv",
                source_type="arxiv",
                topic_id=self._topic_id,
                prompt_override=self._prompt_override,
                metadata={
                    "arxiv_id": e.arxiv_id,
                    "title": e.title,
                    "abstract": e.abstract,
                    "pdf_url": e.pdf_url,
                    "authors": e.authors or [],
                    "published": e.published,
                },
            ))
        logger.info("arxiv_discover_complete", count=len(jobs))
        return jobs

    def fetch(self, job: ScrapeJob) -> Optional[ScrapedArticle]:
        """Fetch article content, extracting PDF sections when available."""
        sections: dict = {}
        pdf_available = False
        pdf_full_text = ""
        pdf_url = job.metadata.get("pdf_url")

        if self._fetch_pdf and pdf_url and self._pdf_parser:
            pdf_full_text = self._pdf_parser.parse(pdf_url)
            if (pdf_full_text or "").strip():  # scanned PDFs produce whitespace-only output
                pdf_available = True
                raw = self._pdf_parser.extract_sections(pdf_full_text)
                sections = {k: v.replace("\x00", "") for k, v in raw.items()}

        return ScrapedArticle(
            url=job.url,
            title=job.metadata.get("title") or job.metadata.get("arxiv_id", job.url),
            content=job.metadata.get("abstract", ""),
            source="arxiv",
            topic_id=job.topic_id,
            published_at=job.metadata.get("published"),
            authors=job.metadata.get("authors", []),
            extra={
                "arxiv_id": job.metadata.get("arxiv_id"),
                "abstract": job.metadata.get("abstract"),
                "pdf_available": pdf_available,
                "sections": sections,
                "original_source": "arxiv",
            },
            full_text=pdf_full_text,
        )

    def _build_query(self) -> str:
        """Construct the arXiv search query from keywords and categories."""
        if self._keywords:
            kw_clause = " OR ".join(self._keywords)
        else:
            kw_clause = (
                'ti:"digital twin" OR ti:"digital twins"'
                ' OR abs:"digital twin" OR abs:"cyber-physical"'
            )
        if self._categories:
            cat_clause = " OR ".join(f"cat:{c}" for c in self._categories)
            kw_part = f"({kw_clause})" if " OR " in kw_clause else kw_clause
            cat_part = f"({cat_clause})" if " OR " in cat_clause else cat_clause
            base = f"{cat_part} AND {kw_part}"
        else:
            base = kw_clause

        return base