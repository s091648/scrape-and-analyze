import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from src.scrapers.scrapers.article import ScrapedArticle
from src.scrapers.scrapers.base_scraper import BaseScraper
from src.scrapers.content_parsers.pdf_parser import PdfParser
from src.scrapers.strategy.scrape_task import ScrapeTask
from src.utils.logging import get_logger

logger = get_logger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
_ARXIV_MAX_RETRIES = 3
_ARXIV_RETRY_BACKOFF = 3  # seconds; wait = 3^(attempt+1): 3, 9, 27s


class ArxivScraper(BaseScraper):
    """Scraper for arXiv API. Fetches PDF full-text by default."""

    def __init__(self, max_results: int = 100, days_back: int = 7,
                 fetch_pdf: bool = True) -> None:
        self.max_results = max_results
        self.days_back = days_back
        self.fetch_pdf = fetch_pdf
        self._pdf_parser = PdfParser() if fetch_pdf else None

    # ── Public API ────────────────────────────────────────────────────────

    def discover(self) -> List[ScrapeTask]:
        """
        Call arXiv API, parse Atom feed, return one ScrapeTask per article.
        Each task's execute() fetches PDF (if enabled) and builds the article.
        Returns [] on API or parse failure.
        """
        from src.observability.metrics import SCRAPER_ARTICLES_FOUND

        entries = self._fetch_entries()
        tasks = [
            ScrapeTask(
                url=e["url"],
                source="arxiv",
                metadata={"arxiv_id": e["arxiv_id"]},
                _execute_fn=lambda d=e: self._build_article(d),
            )
            for e in entries
        ]
        SCRAPER_ARTICLES_FOUND.add(len(tasks), {"source": "arxiv"})
        logger.info("arxiv_discover_complete", task_count=len(tasks))
        return tasks

    # ── Private helpers ───────────────────────────────────────────────────

    def _build_query(self) -> str:
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
        # Fallback to hardcoded defaults if DB is unavailable
        return 'ti:"digital twin" OR ti:"digital twins" OR abs:"digital twin" OR abs:"cyber-physical"'

    def _fetch_entries(self) -> List[dict]:
        """Fetch and parse the arXiv Atom feed. Returns list of entry dicts."""
        params = {
            "search_query": self._build_query(),
            "start": 0,
            "max_results": self.max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        for attempt in range(_ARXIV_MAX_RETRIES + 1):
            try:
                response = requests.get(
                    ARXIV_API_URL, params=params, timeout=60,
                    headers={"User-Agent": "Digital-Twins-Scraper/1.0"},
                )
                response.raise_for_status()
                break
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429 and attempt < _ARXIV_MAX_RETRIES:
                    wait = _ARXIV_RETRY_BACKOFF ** (attempt + 1)
                    logger.warning("arxiv_rate_limited",
                                   attempt=attempt + 1, retry_in_seconds=wait)
                    time.sleep(wait)
                    continue
                logger.error("arxiv_fetch_failed", error=str(e))
                return []
            except Exception as e:
                logger.error("arxiv_fetch_failed", error=str(e))
                return []
        else:
            logger.error("arxiv_fetch_failed", error="max retries exceeded on 429")
            return []

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            logger.error("arxiv_parse_failed", error=str(e))
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.days_back)
        entries = []
        for entry in root.findall(f"{ATOM_NS}entry"):
            data = self._parse_entry(entry)
            if data is None:
                continue
            try:
                pub_date = datetime.fromisoformat(
                    data["published"].replace("Z", "+00:00")
                )
                if pub_date < cutoff:
                    continue
            except (ValueError, AttributeError):
                pass
            entries.append(data)
        return entries

    def _parse_entry(self, entry) -> Optional[dict]:
        id_elem = entry.find(f"{ATOM_NS}id")
        title_elem = entry.find(f"{ATOM_NS}title")
        summary_elem = entry.find(f"{ATOM_NS}summary")
        published_elem = entry.find(f"{ATOM_NS}published")

        arxiv_id = id_elem.text if id_elem is not None else ""
        title = title_elem.text.strip() if title_elem is not None else ""
        summary = (summary_elem.text or "").strip() if summary_elem is not None else ""
        published = published_elem.text if published_elem is not None else ""

        authors = [
            name_elem.text
            for author in entry.findall(f"{ATOM_NS}author")
            for name_elem in [author.find(f"{ATOM_NS}name")]
            if name_elem is not None
        ]

        url = next(
            (link.get("href", "") for link in entry.findall(f"{ATOM_NS}link")
             if link.get("rel") == "alternate"),
            arxiv_id,
        )
        pdf_url = arxiv_id.replace("/abs/", "/pdf/") if "/abs/" in arxiv_id else ""

        return {
            "url": url or arxiv_id,
            "arxiv_id": arxiv_id,
            "title": title,
            "summary": summary,
            "published": published,
            "authors": authors,
            "pdf_url": pdf_url,
        }

    def _build_article(self, entry_data: dict) -> Optional[ScrapedArticle]:
        summary = entry_data["summary"]
        pdf_url = entry_data["pdf_url"]
        pdf_available = False

        if self.fetch_pdf and pdf_url:
            full_text = self._pdf_parser.parse(pdf_url)
            if full_text:
                content = full_text
                pdf_available = True
            else:
                content = summary
        else:
            content = summary

        return ScrapedArticle(
            url=entry_data["url"],
            title=entry_data["title"],
            content=content,
            published_at=entry_data["published"],
            source="arxiv",
            metadata={
                "authors": entry_data["authors"],
                "arxiv_id": entry_data["arxiv_id"],
                "abstract": summary,
                "pdf_available": pdf_available,
            },
        )