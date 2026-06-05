import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests

from src.shared.logging import get_logger

logger = get_logger(__name__)

OPENALEX_API_URL = "https://api.openalex.org/works"
OPENALEX_SELECT_FIELDS = ",".join([
    "id", "title", "abstract_inverted_index", "authorships",
    "publication_date", "open_access", "doi", "ids",
    "cited_by_count", "primary_location",
])


class OpenAlexRateLimitedError(Exception):
    """OpenAlex API returned HTTP 429."""


@dataclass
class OpenAlexEntry:
    work_id: str
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


def _reconstruct_abstract(inverted_index: Optional[dict]) -> str:
    if not inverted_index:
        return ""
    word_positions: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort()
    return " ".join(w for _, w in word_positions)


class OpenAlexClient:
    """
    Thin HTTP + JSON adapter for the OpenAlex Works API.

    Uses the polite pool (mailto in User-Agent) for 10 req/sec.
    No API key required.
    """

    def __init__(self, mailto: Optional[str] = None, http_client=None) -> None:
        self._mailto = mailto or os.environ.get("OPENALEX_MAILTO", "")
        if http_client is None:
            from src.infrastructure.shared.http import get_default_client
            http_client = get_default_client()
        self._http = http_client

    def fetch_papers(
        self,
        query: str,
        max_results: int = 20,
        days_back: Optional[int] = None,
    ) -> List[OpenAlexEntry]:
        filters = []
        if days_back is not None and days_back > 0:
            from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
            filters.append(f"from_publication_date:{from_date}")

        params: dict = {
            "search": query,
            "per_page": min(max_results, 200),
            "sort": "publication_date:desc",
            "select": OPENALEX_SELECT_FIELDS,
        }
        if filters:
            params["filter"] = ",".join(filters)

        ua_suffix = f" (mailto:{self._mailto})" if self._mailto else ""
        headers = {"User-Agent": f"scrape-analyzer/1.0{ua_suffix}"}

        try:
            response = self._http.get(
                OPENALEX_API_URL,
                params=params,
                headers=headers,
                timeout=60,
            )
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                logger.warning("openalex_rate_limited", url=OPENALEX_API_URL)
                raise OpenAlexRateLimitedError(str(exc)) from exc
            logger.error("openalex_fetch_failed", error=str(exc))
            return []
        except Exception as e:
            logger.error("openalex_fetch_failed", error=str(e))
            return []

        try:
            results = response.json().get("results", [])
        except Exception as e:
            logger.error("openalex_fetch_failed", error=str(e))
            return []

        entries = [e for paper in results if (e := self._parse_entry(paper)) is not None]
        logger.info("openalex_entries_fetched", count=len(entries))
        return entries

    def _parse_entry(self, paper: dict) -> Optional[OpenAlexEntry]:
        try:
            work_id = paper.get("id", "")
            title = paper.get("title") or ""
            abstract = _reconstruct_abstract(paper.get("abstract_inverted_index"))
            authors = [
                a["author"]["display_name"]
                for a in (paper.get("authorships") or [])
                if a.get("author", {}).get("display_name")
            ]
            publication_date = paper.get("publication_date")
            citation_count = paper.get("cited_by_count", 0)

            ids = paper.get("ids") or {}
            doi_url = ids.get("doi") or paper.get("doi")
            doi = doi_url.replace("https://doi.org/", "") if doi_url else None

            arxiv_url = ids.get("arxiv")
            arxiv_id = arxiv_url.replace("https://arxiv.org/abs/", "") if arxiv_url else None

            open_access = paper.get("open_access") or {}
            is_open_access = open_access.get("is_oa", False)
            oa_url = open_access.get("oa_url")

            primary_location = paper.get("primary_location") or {}
            pdf_url = primary_location.get("pdf_url") or oa_url

            if arxiv_id:
                url = f"https://arxiv.org/abs/{arxiv_id}"
            elif doi:
                url = f"https://doi.org/{doi}"
            else:
                url = work_id  # OpenAlex URL

            return OpenAlexEntry(
                work_id=work_id,
                url=url,
                title=title,
                abstract=abstract,
                authors=authors,
                publication_date=publication_date,
                open_access_pdf_url=pdf_url,
                doi=doi,
                arxiv_id=arxiv_id,
                citation_count=citation_count,
                is_open_access=is_open_access,
            )
        except Exception as e:
            logger.warning("openalex_parse_entry_failed", error=str(e))
            return None
