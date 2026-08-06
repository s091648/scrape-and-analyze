"""
ArxivClient — infrastructure adapter for the arXiv Export API.

Responsibility: HTTP request + Atom XML parsing only.
No domain logic (keyword building, date filtering, PDF fetching) lives here.
Those decisions stay in ArxivScraper (ingestion bounded context).

Accepts an HttpClient so rate limiting, retry, and single-connection
semaphore are handled transparently by the shared infrastructure.
"""
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests

from src.infrastructure.shared.http import get_api_bot_ua
from src.shared.logging import get_logger

logger = get_logger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"


class ArxivRateLimitedError(Exception):
    """arXiv API returned HTTP 429. Signals callers to abort remaining arxiv tasks for this run."""


def normalize_arxiv_id(raw: str) -> str:
    """Strip arXiv's URL form (e.g. "http://arxiv.org/abs/2606.29232v1") and any
    trailing version suffix down to the bare id ("2606.29232") external lookups
    like Semantic Scholar's paper/ARXIV:<id> require. Already-bare ids pass
    through unchanged. Shared with scripts/data/versions/ backfill migrations
    that clean up rows persisted before this normalization existed."""
    return re.sub(r"v\d+$", "", raw.rsplit("/abs/", 1)[-1])


@dataclass
class ArxivEntry:
    """Parsed representation of a single arXiv paper entry from the Atom feed."""
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

    Accepts an HttpClient so rate limiting, retry, and single-connection
    semaphore are handled transparently by the shared infrastructure.
    Pass a custom http_client in tests to inject a mock.
    """

    def __init__(self, http_client=None) -> None:
        if http_client is None:
            from src.infrastructure.shared.http import get_default_client
            http_client = get_default_client().with_skip_retry_status(frozenset({429}))
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
            # Use descriptive bot UA per arXiv API TOS (not browser UA rotation).
            response = self._http.get(
                ARXIV_API_URL,
                params=params,
                timeout=60,
                headers={"User-Agent": get_api_bot_ua()},
            )
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                logger.warning("arxiv_rate_limited", url=ARXIV_API_URL)
                raise ArxivRateLimitedError(str(exc)) from exc
            logger.error("arxiv_fetch_failed", error=str(exc))
            return []
        except Exception as e:
            logger.error("arxiv_fetch_failed", error=str(e))
            return []

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            logger.error("arxiv_parse_failed",
                         error=str(e),
                         content_preview=response.content[:200].decode("utf-8", errors="replace"))
            return []

        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
            if days_back is not None
            else None
        )

        raw_entries = root.findall(f"{ATOM_NS}entry")
        logger.debug("arxiv_raw_entries", count=len(raw_entries),
                     cutoff=cutoff.isoformat() if cutoff else None)

        entries = []
        for elem in raw_entries:
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
        """Parse a single Atom <entry> element into an ArxivEntry, or None on failure."""
        id_elem = elem.find(f"{ATOM_NS}id")
        title_elem = elem.find(f"{ATOM_NS}title")
        summary_elem = elem.find(f"{ATOM_NS}summary")
        published_elem = elem.find(f"{ATOM_NS}published")

        raw_id = (id_elem.text or "").strip() if id_elem is not None else ""
        # arXiv's Atom <id> is a URL, not a bare identifier — keep raw_id below for
        # url/pdf_url, which do need the full URL form; normalize arxiv_id itself.
        arxiv_id = normalize_arxiv_id(raw_id)
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
            raw_id,
        )
        pdf_url = raw_id.replace("/abs/", "/pdf/") if "/abs/" in raw_id else ""

        return ArxivEntry(
            arxiv_id=arxiv_id,
            url=url or raw_id,
            pdf_url=pdf_url,
            title=title,
            abstract=abstract,
            published=published,
            authors=authors,
        )
