from typing import List, Optional
from uuid import UUID

from src.shared.logging import get_logger
from src.infrastructure.collection.clients import ArxivClient
from .base_scraper import BaseScraper
from src.modules.collection.application.events import ArticleScrapedEvent
from src.modules.collection.domain.entities import ScrapeJob, ScrapeJobMetadata
from src.infrastructure.collection.parsers import PdfParser
from src.infrastructure.shared.observability.otel_metrics import SCRAPER_ARTICLES_FOUND

logger = get_logger(__name__)


class ArxivScraper(BaseScraper):

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
        self._client = client or ArxivClient()
        self._pdf_parser = PdfParser() if fetch_pdf else None

    def discover(self) -> List[ScrapeJob]:
        query = self._build_query()
        entries = self._client.fetch_entries(
            query=query,
            max_results=self._max_results,
            days_back=self._days_back,
        )
        jobs = []
        for e in entries:
            metadata = ScrapeJobMetadata(
                arxiv_id=e.arxiv_id,
                abstract=e.abstract,
                pdf_url=e.pdf_url,
                authors=e.authors,
                published=e.published,
            )
            jobs.append(ScrapeJob(
                url=e.url,
                source="arxiv",
                source_type="arxiv",
                topic_id=self._topic_id,
                prompt_override=self._prompt_override,
                metadata=metadata,
            ))
        SCRAPER_ARTICLES_FOUND.add(len(jobs), {"source": "arxiv"})
        logger.info("arxiv_discover_complete", count=len(jobs))
        return jobs

    def fetch(self, job: ScrapeJob) -> Optional[ArticleScrapedEvent]:
        sections: dict = {}
        pdf_available = False
        pdf_url = job.metadata.get("pdf_url")

        if self._fetch_pdf and pdf_url and self._pdf_parser:
            full_text = self._pdf_parser.parse(pdf_url)
            if full_text:
                pdf_available = True
                raw_sections = self._pdf_parser.extract_sections(full_text)
                sections = {
                    name: body.replace("\x00", "")
                    for name, body in raw_sections.items()
                }

        return ArticleScrapedEvent(
            url=job.url,
            title=job.metadata.get("arxiv_id", job.url),
            content=job.metadata.get("abstract", ""),
            source="arxiv",
            topic_id=job.topic_id,
            published_at=job.metadata.get("published"),
            metadata={
                "authors": job.metadata.get("authors", []),
                "arxiv_id": job.metadata.get("arxiv_id"),
                "abstract": job.metadata.get("abstract"),
                "pdf_available": pdf_available,
                "sections": sections,
            },
        )

    def _build_query(self) -> str:
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
            return f"{cat_part} AND {kw_part}"
        return kw_clause
