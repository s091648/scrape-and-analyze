"""
SemanticScholarClient — infrastructure adapter for the Semantic Scholar Graph API.

Responsibility: HTTP request + JSON parsing only.
No domain logic (keyword building, date filtering, PDF fetching) lives here.
Those decisions stay in SemanticScholarScraper (ingestion bounded context).

Accepts an HttpClient so rate limiting, retry, and single-connection
semaphore are handled transparently by the shared infrastructure.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests

from src.config.settings import SEMANTIC_SCHOLAR_API_KEY
from src.shared.logging import get_logger

logger = get_logger(__name__)

SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_SCHOLAR_FIELDS = (
    "paperId,title,abstract,authors,publicationDate,year,"
    "openAccessPdf,externalIds,isOpenAccess,citationCount"
)


class SemanticScholarRateLimitedError(Exception):
    """Semantic Scholar API returned HTTP 429. Signals callers to abort remaining tasks for this run."""


@dataclass
class SemanticScholarEntry:
    """Parsed representation of a single paper from the Semantic Scholar Graph API."""
    paper_id: str
    url: str
    title: str
    abstract: str
    authors: List[str] = field(default_factory=list)
    publication_date: Optional[str] = None
    open_access_pdf_url: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    citation_count: int = 0
    is_open_access: bool = False
    original_source: Optional[str] = None  # e.g. "arxiv", "semanticscholar"


class SemanticScholarClient:
    """
    Thin HTTP + JSON adapter for the Semantic Scholar Graph API.

    Accepts an HttpClient so rate limiting, retry, and single-connection
    semaphore are handled transparently by the shared infrastructure.
    Pass a custom http_client in tests to inject a mock.
    """

    def __init__(self, api_key: Optional[str] = None, http_client=None) -> None:
        self._api_key = api_key or SEMANTIC_SCHOLAR_API_KEY
        if http_client is None:
            from src.infrastructure.shared.http import get_default_client
            http_client = get_default_client()
        self._http = http_client

    def fetch_by_doi(self, doi: str) -> Optional[dict]:
        """Fetch a single paper by DOI. Returns the raw parsed JSON dict (not a
        SemanticScholarEntry) so metric extractors can evaluate JMESPath
        expressions against Semantic Scholar's actual field names (e.g. 'citationCount')."""
        headers = {"x-api-key": self._api_key} if self._api_key else {}
        try:
            response = self._http.get(
                f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
                params={"fields": SEMANTIC_SCHOLAR_FIELDS},
                headers=headers,
                timeout=30,
            )
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                logger.warning("semantic_scholar_rate_limited", url="paper/DOI:" + doi)
                raise SemanticScholarRateLimitedError(str(exc)) from exc
            logger.error("semantic_scholar_fetch_by_doi_failed", doi=doi, error=str(exc))
            return None
        except Exception as e:
            logger.error("semantic_scholar_fetch_by_doi_failed", doi=doi, error=str(e))
            return None

        try:
            return response.json()
        except Exception as e:
            logger.error("semantic_scholar_fetch_by_doi_failed", doi=doi, error=str(e))
            return None

    def fetch_papers(
        self,
        query: str,
        max_results: int = 20,
        days_back: Optional[int] = None,
    ) -> List[SemanticScholarEntry]:
        """
        Call the Semantic Scholar API and return parsed entries.

        Args:
            query:       search query string.
            max_results: max number of results to request (capped at 100).
            days_back:   if set, filter to papers from the last N days.
        Returns:
            List of SemanticScholarEntry; empty list on network or parse failure.
        """
        params: dict = {
            "query": query,
            "fields": SEMANTIC_SCHOLAR_FIELDS,
            "limit": min(max_results, 100),
            "sort": "PublicationDate:desc",
        }

        if days_back is not None and days_back > 0:
            from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
            params["publicationDateOrYear"] = f"{from_date}:"

        headers = {"x-api-key": self._api_key} if self._api_key else {}

        try:
            response = self._http.get(
                SEMANTIC_SCHOLAR_API_URL,
                params=params,
                headers=headers,
                timeout=60,
            )
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                logger.warning("semantic_scholar_rate_limited", url=SEMANTIC_SCHOLAR_API_URL)
                raise SemanticScholarRateLimitedError(str(exc)) from exc
            logger.error("semantic_scholar_fetch_failed", error=str(exc))
            return []
        except Exception as e:
            logger.error("semantic_scholar_fetch_failed", error=str(e))
            return []

        try:
            data = response.json().get("data", [])
        except Exception as e:
            logger.error("semantic_scholar_fetch_failed", error=str(e))
            return []

        entries = []
        for paper in data:
            entry = self._parse_entry(paper)
            if entry is not None:
                entries.append(entry)

        logger.info("semantic_scholar_entries_fetched", count=len(entries))
        return entries

    # ── private ───────────────────────────────────────────────────────────

    def _parse_entry(self, paper: dict) -> Optional[SemanticScholarEntry]:
        """Parse a single Semantic Scholar paper dict into an entry, or None on failure."""
        try:
            paper_id = paper.get("paperId", "")
            title = paper.get("title") or ""
            abstract = paper.get("abstract") or ""
            authors = [a.get("name", "") for a in (paper.get("authors") or [])]
            publication_date = paper.get("publicationDate") or (
                str(paper.get("year")) if paper.get("year") else None
            )
            external_ids = paper.get("externalIds") or {}
            arxiv_id = external_ids.get("ArXiv")
            doi = external_ids.get("DOI")
            open_access_pdf = paper.get("openAccessPdf") or {}
            open_access_pdf_url = open_access_pdf.get("url") if open_access_pdf else None
            is_open_access = paper.get("isOpenAccess", False)
            citation_count = paper.get("citationCount", 0)

            if arxiv_id:
                url = f"https://arxiv.org/abs/{arxiv_id}"
                original_source = "arxiv"
            else:
                url = f"https://www.semanticscholar.org/paper/{paper_id}"
                original_source = "semanticscholar"

            return SemanticScholarEntry(
                paper_id=paper_id,
                url=url,
                title=title,
                abstract=abstract,
                authors=authors,
                publication_date=publication_date,
                open_access_pdf_url=open_access_pdf_url,
                doi=doi,
                arxiv_id=arxiv_id,
                citation_count=citation_count,
                is_open_access=is_open_access,
                original_source=original_source,
            )
        except Exception as e:
            logger.warning("semantic_scholar_parse_entry_failed", error=str(e))
            return None
