"""
ArxivClient — infrastructure adapter for the arXiv Export API.

Responsibility: HTTP request + Atom XML parsing only.
No domain logic (keyword building, date filtering, PDF fetching) lives here.
Those decisions stay in ArxivScraper (ingestion bounded context).
"""
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from src.infrastructure.shared.http.user_agent import get_api_bot_ua
from src.infrastructure.shared.logging import get_logger

logger = get_logger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"


@dataclass
class ArxivEntry:
    arxiv_id: str
    url: str
    pdf_url: str
    title: str
    abstract: str
    published: str
    authors: List[str] = field(default_factory=list)


class ArxivClient:
    """
    Thin HTTP + XML adapter for the arXiv Atom feed API.

    Accepts an HttpClient (from infrastructure.http) so rate limiting,
    retry, and UA rotation are handled transparently.
    """

    def __init__(self, http_client=None) -> None:
        if http_client is None:
            from src.infrastructure.shared.http import get_default_client
            http_client = get_default_client()
        self._http = http_client

    def fetch_entries(
        self,
        query: str,
        max_results: int = 30,
        days_back: Optional[int] = None,
    ) -> List[ArxivEntry]:
        """
        Call the arXiv API and return parsed entries.

        Args:
            query:       arXiv search query string.
            max_results: max number of results to request.
            days_back:   if set, filter out entries older than N days.
        Returns:
            List of ArxivEntry; empty list on network or parse failure.
        """
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        try:
            # Use descriptive bot UA per arXiv API TOS (not browser UA rotation)
            response = self._http.get(
                ARXIV_API_URL,
                params=params,
                timeout=60,
                headers={"User-Agent": get_api_bot_ua()},
            )
        except Exception as e:
            logger.error("arxiv_fetch_failed", error=str(e))
            return []

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            logger.error("arxiv_parse_failed", error=str(e))
            return []

        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
            if days_back is not None
            else None
        )

        entries = []
        for elem in root.findall(f"{ATOM_NS}entry"):
            entry = self._parse_entry(elem)
            if entry is None:
                continue
            if cutoff is not None and entry.published:
                try:
                    pub_dt = datetime.fromisoformat(
                        entry.published.replace("Z", "+00:00")
                    )
                    if pub_dt < cutoff:
                        continue
                except (ValueError, AttributeError):
                    pass
            entries.append(entry)

        logger.info("arxiv_entries_fetched", count=len(entries))
        return entries

    # ── private ───────────────────────────────────────────────────────────

    def _parse_entry(self, elem) -> Optional[ArxivEntry]:
        id_elem = elem.find(f"{ATOM_NS}id")
        title_elem = elem.find(f"{ATOM_NS}title")
        summary_elem = elem.find(f"{ATOM_NS}summary")
        published_elem = elem.find(f"{ATOM_NS}published")

        arxiv_id = (id_elem.text or "").strip() if id_elem is not None else ""
        title = (title_elem.text or "").strip() if title_elem is not None else ""
        abstract = (summary_elem.text or "").strip() if summary_elem is not None else ""
        published = (published_elem.text or "").strip() if published_elem is not None else ""

        authors = [
            name_elem.text
            for author in elem.findall(f"{ATOM_NS}author")
            for name_elem in [author.find(f"{ATOM_NS}name")]
            if name_elem is not None and name_elem.text
        ]

        url = next(
            (
                link.get("href", "")
                for link in elem.findall(f"{ATOM_NS}link")
                if link.get("rel") == "alternate"
            ),
            arxiv_id,
        )
        pdf_url = arxiv_id.replace("/abs/", "/pdf/") if "/abs/" in arxiv_id else ""

        return ArxivEntry(
            arxiv_id=arxiv_id,
            url=url or arxiv_id,
            pdf_url=pdf_url,
            title=title,
            abstract=abstract,
            published=published,
            authors=authors,
        )
