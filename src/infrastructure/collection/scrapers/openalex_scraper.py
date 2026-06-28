from typing import List, Optional
from uuid import UUID

from src.shared.logging import get_logger
from src.infrastructure.collection.clients.openalex_client import OpenAlexClient, OpenAlexRateLimitedError
from .base_scraper import BaseScraper
from src.modules.collection.domain.entities import ScrapeJob
from src.modules.collection.domain.value_objects import ScrapedArticle
from src.infrastructure.collection.parsers import PdfParser

logger = get_logger(__name__)


class OpenAlexScraper(BaseScraper):
    """Discovers and fetches academic papers from the OpenAlex Works API."""

    def __init__(
        self,
        max_results: int = 20,
        days_back: int = 7,
        fetch_pdf: bool = True,
        keywords: Optional[List[str]] = None,
        topic_id: Optional[UUID] = None,
        prompt_override: Optional[str] = None,
        client: OpenAlexClient = None,
    ) -> None:
        self._max_results = max_results
        self._days_back = days_back
        self._fetch_pdf = fetch_pdf
        self._keywords = keywords
        self._topic_id = topic_id
        self._prompt_override = prompt_override
        self._client = client or OpenAlexClient()
        self._pdf_parser = PdfParser() if fetch_pdf else None

    def discover(self) -> List[ScrapeJob]:
        """Query the OpenAlex API and return ScrapeJobs for matching works."""
        query = self._build_query()
        if not query:
            return []
        try:
            entries = self._client.fetch_papers(
                query=query,
                max_results=self._max_results,
                days_back=self._days_back if self._days_back > 0 else None,
            )
        except OpenAlexRateLimitedError as e:
            logger.warning("openalex_rate_limited", message=str(e))
            return []
        jobs = []
        for e in entries:
            jobs.append(ScrapeJob(
                url=e.url,
                source="openalex",
                source_type="openalex",
                topic_id=self._topic_id,
                prompt_override=self._prompt_override,
                metadata={
                    "work_id": e.work_id,
                    "title": e.title,
                    "abstract": e.abstract,
                    "open_access_pdf_url": e.open_access_pdf_url,
                    "doi": e.doi,
                    "arxiv_id": e.arxiv_id,
                    "citation_count": e.citation_count,
                    "is_open_access": e.is_open_access,
                    "authors": e.authors or [],
                    "published": e.publication_date,
                    "via_source": "openalex",
                    "original_source": e.original_source,
                    "primary_topic": e.primary_topic,
                    "primary_field": e.primary_field,
                },
            ))
        logger.info("openalex_discover_complete", count=len(jobs))
        return jobs

    def fetch(self, job: ScrapeJob) -> Optional[ScrapedArticle]:
        """Fetch article content, extracting PDF sections when available."""
        sections: dict = {}
        pdf_available = False
        pdf_full_text = ""
        pdf_url = job.metadata.get("open_access_pdf_url")

        if self._fetch_pdf and pdf_url and self._pdf_parser:
            pdf_full_text = self._pdf_parser.parse(pdf_url)
            if (pdf_full_text or "").strip():  # scanned PDFs produce whitespace-only output
                pdf_available = True
                raw_sections = self._pdf_parser.extract_sections(pdf_full_text)
                sections = {
                    name: body.replace("\x00", "")
                    for name, body in raw_sections.items()
                }

        return ScrapedArticle(
            url=job.url,
            title=job.metadata.get("title") or job.metadata.get("work_id", job.url),
            content=job.metadata.get("abstract", ""),
            source="openalex",
            topic_id=job.topic_id,
            published_at=job.metadata.get("published"),
            authors=job.metadata.get("authors", []),
            citation_count=job.metadata.get("citation_count"),
            extra={
                "work_id": job.metadata.get("work_id"),
                "abstract": job.metadata.get("abstract"),
                "doi": job.metadata.get("doi"),
                "arxiv_id": job.metadata.get("arxiv_id"),
                "citation_count": job.metadata.get("citation_count", 0),
                "is_open_access": job.metadata.get("is_open_access", False),
                "pdf_available": pdf_available,
                "sections": sections,
                "via_source": "openalex",
                "original_source": job.metadata.get("original_source"),
                "primary_topic": job.metadata.get("primary_topic"),
                "primary_field": job.metadata.get("primary_field"),
            },
            full_text=pdf_full_text,
        )

    def _build_query(self) -> str:
        """Build the search query string from configured keywords."""
        if not self._keywords:
            return ""
        return " ".join(self._keywords)
