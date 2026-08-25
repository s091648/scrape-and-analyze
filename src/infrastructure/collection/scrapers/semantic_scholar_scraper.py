from typing import List, Optional
from uuid import UUID
from src.shared.logging import get_logger
from src.infrastructure.collection.clients import SemanticScholarClient, SemanticScholarRateLimitedError
from .base_scraper import BaseScraper
from src.modules.collection.domain.entities import ScrapeJob
from src.modules.collection.domain.value_objects import ScrapedArticle
from src.infrastructure.collection.parsers import PdfParser

logger = get_logger(__name__)


class SemanticScholarScraper(BaseScraper):
    """Discovers and fetches academic papers from the Semantic Scholar Graph API."""

    def __init__(
        self,
        max_results: int = 20,
        days_back: int = 7,
        fetch_pdf: bool = True,
        keywords: Optional[List[str]] = None,
        topic_id: Optional[UUID] = None,
        prompt_override: Optional[str] = None,
        client: SemanticScholarClient = None,
    ) -> None:
        self._max_results = max_results
        self._days_back = days_back
        self._fetch_pdf = fetch_pdf
        self._keywords = keywords
        self._topic_id = topic_id
        self._prompt_override = prompt_override
        self._client = client or SemanticScholarClient()
        self._pdf_parser = PdfParser() if fetch_pdf else None

    def discover(self) -> List[ScrapeJob]:
        """Query the Semantic Scholar API and return ScrapeJobs for matching papers."""
        query = self._build_query()
        if not query:
            return []
        try:
            entries = self._client.fetch_papers(
                query=query,
                max_results=self._max_results,
                days_back=self._days_back if self._days_back > 0 else None,
            )
        except SemanticScholarRateLimitedError as e:
            logger.warning("semantic_scholar_rate_limited", message=str(e))
            raise
        jobs = []
        for e in entries:
            jobs.append(ScrapeJob(
                url=e.url,
                source="semantic_scholar",
                source_type="semantic_scholar",
                topic_id=self._topic_id,
                prompt_override=self._prompt_override,
                metadata={
                    "paper_id": e.paper_id,
                    "title": e.title,
                    "abstract": e.abstract,
                    "open_access_pdf_url": e.open_access_pdf_url,
                    "doi": e.doi,
                    "arxiv_id": e.arxiv_id,
                    "citation_count": e.citation_count,
                    "is_open_access": e.is_open_access,
                    "authors": e.authors or [],
                    "published": e.publication_date,
                    "via_source": "semantic_scholar",
                    "original_source": e.original_source,
                },
            ))
        logger.info("semantic_scholar_discover_complete", count=len(jobs))
        return jobs

    def fetch(self, job: ScrapeJob) -> Optional[ScrapedArticle]:
        """Fetch article content, extracting PDF sections when available."""
        sections: dict = {}
        pdf_available = False
        pdf_url = job.metadata.get("open_access_pdf_url")

        if self._fetch_pdf and pdf_url and self._pdf_parser:
            full_text = self._pdf_parser.parse(pdf_url)
            if full_text:
                pdf_available = True
                raw_sections = self._pdf_parser.extract_sections(full_text)
                sections = {
                    name: body.replace("\x00", "")
                    for name, body in raw_sections.items()
                }

        return ScrapedArticle(
            url=job.url,
            title=job.metadata.get("title") or job.metadata.get("paper_id", job.url),
            content=job.metadata.get("abstract", ""),
            source="semantic_scholar",
            topic_id=job.topic_id,
            published_at=self._parse_published_at(job.metadata.get("published")),
            authors=job.metadata.get("authors", []),
            extra={
                "paper_id": job.metadata.get("paper_id"),
                "abstract": job.metadata.get("abstract"),
                "doi": job.metadata.get("doi"),
                "arxiv_id": job.metadata.get("arxiv_id"),
                "citation_count": job.metadata.get("citation_count", 0),
                "is_open_access": job.metadata.get("is_open_access", False),
                "pdf_available": pdf_available,
                "sections": sections,
                "via_source": "semantic_scholar",
                "original_source": job.metadata.get("original_source"),
            },
        )

    def _build_query(self) -> str:
        """Build the search query string from configured keywords."""
        if not self._keywords:
            return ""
        return " ".join(self._keywords)
