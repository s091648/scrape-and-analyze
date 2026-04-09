from typing import List, Optional

from src.infrastructure.external.arxiv_client import ArxivClient, ArxivEntry
from src.ingestion.models.scraped_article import ScrapedArticle
from src.ingestion.scrapers.base_scraper import BaseScraper
from src.ingestion.parsers.pdf_parser import PdfParser
from src.pipeline.task import ScrapeTask
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ArxivScraper(BaseScraper):

    def __init__(
        self,
        max_results: int = 100,
        days_back: int = 7,
        fetch_pdf: bool = True,
        keywords: Optional[List[str]] = None,
        topic_id: Optional[str] = None,
        prompt_override: Optional[str] = None,
        client: ArxivClient = None,
    ) -> None:
        self.max_results = max_results
        self.days_back = days_back
        self.fetch_pdf = fetch_pdf
        self._keywords = keywords  # list of query strings, or None for fallback
        self._topic_id = topic_id
        self._prompt_override = prompt_override
        self._client = client or ArxivClient()
        self._pdf_parser = PdfParser() if fetch_pdf else None

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

    def _build_query(self) -> str:
        if self._keywords:
            return " OR ".join(self._keywords)
        # Hardcoded fallback for backward compatibility
        return (
            'ti:"digital twin" OR ti:"digital twins"'
            ' OR abs:"digital twin" OR abs:"cyber-physical"'
        )

    def _build_article(self, entry: ArxivEntry) -> Optional[ScrapedArticle]:
        sections: dict = {}
        pdf_available = False

        if self.fetch_pdf and entry.pdf_url:
            full_text = self._pdf_parser.parse(entry.pdf_url)
            if full_text:
                pdf_available = True
                raw_sections = self._pdf_parser.extract_sections(full_text)
                # Strip null bytes — PostgreSQL JSONB rejects \u0000
                sections = {
                    name: body.replace("\x00", "")
                    for name, body in raw_sections.items()
                }

        return ScrapedArticle(
            url=entry.url,
            title=entry.title,
            content=entry.abstract,
            published_at=entry.published,
            source="arxiv",
            topic_id=self._topic_id,
            prompt_override=self._prompt_override,
            metadata={
                "authors": entry.authors,
                "arxiv_id": entry.arxiv_id,
                "abstract": entry.abstract,
                "pdf_available": pdf_available,
                "sections": sections,
            },
        )
