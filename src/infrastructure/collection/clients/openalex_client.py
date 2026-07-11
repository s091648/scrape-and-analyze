import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests

from src.config.settings import OPENALEX_MAILTO
from src.shared.logging import get_logger

logger = get_logger(__name__)

OPENALEX_API_URL = "https://api.openalex.org/works"
OPENALEX_SELECT_FIELDS = ",".join([
    "id", "title", "abstract_inverted_index", "authorships",
    "publication_date", "open_access", "doi", "ids",
    "cited_by_count", "primary_location", "primary_topic",
])

# Always-on filters: journal articles only, must have abstract, not retracted.
_BASE_FILTERS = ["type:article", "has_abstract:true", "is_retracted:false"]


class OpenAlexRateLimitedError(Exception):
    """OpenAlex API returned HTTP 429."""


@dataclass
class OpenAlexEntry:
    """Parsed representation of a single work from the OpenAlex API."""
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
    primary_topic: Optional[str] = None
    primary_field: Optional[str] = None
    original_source: Optional[str] = None  # e.g. "arxiv", journal display name


# Cache DOI-prefix → publisher to avoid repeated Crossref calls.
# Keyed by "10.XXXX/" (registrant prefix including slash).
# None means Crossref returned no useful result for that prefix.
_doi_prefix_publisher_cache: dict[str, Optional[str]] = {}


def _extract_doi_registrant(doi: str) -> str:
    """Return the registrant prefix (e.g. '10.1145/') from a DOI string."""
    slash = doi.find("/")
    return doi[: slash + 1] if slash != -1 else doi


_DOI_PREFIX_TO_PUBLISHER: dict[str, str] = {
    "10.1145/": "ACM Digital Library",
    "10.1109/": "IEEE Xplore",
    "10.1007/": "Springer",
    "10.1038/": "Nature",
    "10.1016/": "Elsevier",
    "10.1126/": "Science",
    "10.1002/": "Wiley",
    "10.1093/": "Oxford Academic",
    "10.1017/": "Cambridge",
    "10.1371/": "PLOS",
    "10.3389/": "Frontiers",
    "10.1186/": "BioMed Central",
    "10.1103/": "APS",
    "10.1021/": "ACS Publications",
    "10.1039/": "RSC",
    "10.1073/": "PNAS",
}


def _derive_publisher_from_doi(doi: str) -> Optional[str]:
    """Look up a known publisher from a DOI registrant prefix map."""
    for prefix, publisher in _DOI_PREFIX_TO_PUBLISHER.items():
        if doi.startswith(prefix):
            return publisher
    return None


def _derive_publisher_from_landing_url(url: str) -> Optional[str]:
    """Infer publisher name from known hostname patterns in a landing page URL."""
    if not url:
        return None
    if "acm.org" in url:
        return "ACM Digital Library"
    if "ieee.org" in url:
        return "IEEE Xplore"
    if "springer.com" in url:
        return "Springer"
    if "nature.com" in url:
        return "Nature"
    if "science.org" in url or "sciencemag.org" in url:
        return "Science"
    if "cell.com" in url:
        return "Cell Press"
    if "biorxiv.org" in url:
        return "bioRxiv"
    if "medrxiv.org" in url:
        return "medRxiv"
    if "plos.org" in url:
        return "PLOS"
    if "onlinelibrary.wiley.com" in url or "wiley.com" in url:
        return "Wiley"
    if "sciencedirect.com" in url or "elsevier.com" in url:
        return "Elsevier"
    if "academic.oup.com" in url or "oup.com" in url:
        return "Oxford Academic"
    if "cambridge.org" in url:
        return "Cambridge"
    return None


def _reconstruct_abstract(inverted_index: Optional[dict]) -> str:
    """Reconstruct plain-text abstract from OpenAlex inverted-index format."""
    if not inverted_index:
        return ""
    word_positions: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort()
    return " ".join(w for _, w in word_positions)


CROSSREF_API_URL = "https://api.crossref.org/works"


class OpenAlexClient:
    """
    Thin HTTP + JSON adapter for the OpenAlex Works API.

    Uses the polite pool (mailto in User-Agent) for 10 req/sec.
    No API key required.
    """

    def __init__(self, mailto: Optional[str] = None, http_client=None) -> None:
        self._mailto = mailto or OPENALEX_MAILTO
        if http_client is None:
            from src.infrastructure.shared.http import get_default_client
            http_client = get_default_client()
        self._http = http_client

    def _lookup_publisher_via_crossref(self, doi: str) -> Optional[str]:
        """Query Crossref for publisher info on first encounter of a DOI prefix.

        Results are cached by registrant prefix (e.g. '10.1145/') so that
        only one HTTP call is made per unknown publisher across the lifetime
        of this process, regardless of how many papers share the same prefix.
        """
        prefix = _extract_doi_registrant(doi)
        if prefix in _doi_prefix_publisher_cache:
            return _doi_prefix_publisher_cache[prefix]
        publisher: Optional[str] = None
        try:
            ua_suffix = f" (mailto:{self._mailto})" if self._mailto else ""
            headers = {"User-Agent": f"scrape-analyzer/1.0{ua_suffix}"}
            resp = self._http.get(
                f"{CROSSREF_API_URL}/{doi}",
                headers=headers,
                timeout=10,
            )
            publisher = resp.json().get("message", {}).get("publisher") or None
        except Exception as exc:
            logger.debug("crossref_lookup_failed", doi=doi, error=str(exc))
        _doi_prefix_publisher_cache[prefix] = publisher
        if publisher:
            logger.info("crossref_publisher_resolved", doi_prefix=prefix, publisher=publisher)
        return publisher

    def fetch_by_doi(self, doi: str) -> Optional[dict]:
        """Fetch a single work by DOI. Returns the raw parsed JSON dict (not an
        OpenAlexEntry) so metric extractors can evaluate JMESPath expressions
        against OpenAlex's actual field names (e.g. 'cited_by_count')."""
        ua_suffix = f" (mailto:{self._mailto})" if self._mailto else ""
        headers = {"User-Agent": f"scrape-analyzer/1.0{ua_suffix}"}
        try:
            response = self._http.get(
                f"{OPENALEX_API_URL}/doi:{doi}",
                headers=headers,
                timeout=30,
            )
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                logger.warning("openalex_rate_limited", url=OPENALEX_API_URL)
                raise OpenAlexRateLimitedError(str(exc)) from exc
            logger.error("openalex_fetch_by_doi_failed", doi=doi, error=str(exc))
            return None
        except Exception as e:
            logger.error("openalex_fetch_by_doi_failed", doi=doi, error=str(e))
            return None

        try:
            return response.json()
        except Exception as e:
            logger.error("openalex_fetch_by_doi_failed", doi=doi, error=str(e))
            return None

    def fetch_papers(
        self,
        query: str,
        max_results: int = 20,
        days_back: Optional[int] = None,
    ) -> List[OpenAlexEntry]:
        """Search OpenAlex for papers matching query; returns parsed entries, empty list on failure."""
        filters = list(_BASE_FILTERS)
        if days_back is not None and days_back > 0:
            from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
            filters.append(f"from_publication_date:{from_date}")

        params: dict = {
            "search": query,
            "per_page": min(max_results, 200),
            # relevance_score ranks by how well the paper matches the query;
            # previously date-only sort returned off-topic recent papers.
            "sort": "relevance_score:desc",
            "select": OPENALEX_SELECT_FIELDS,
            "filter": ",".join(filters),
        }

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
        """Parse a single OpenAlex work dict into an OpenAlexEntry, or None on failure."""
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

            topic_obj = paper.get("primary_topic") or {}
            primary_topic = topic_obj.get("display_name")
            primary_field = (topic_obj.get("field") or {}).get("display_name")

            # Resolve original_source via 4-level fallback:
            # 1. arxiv_id present → known preprint repository, always "arxiv"
            # 2. primary_location.source.display_name → OpenAlex-provided journal/venue name
            # 3. landing_page_url hostname → publisher detected from the article landing URL
            # 4. DOI registrant prefix map → well-known publisher from static dict (e.g. 10.1145/ → ACM)
            # 5. Crossref API → live lookup for unknown prefixes, cached per DOI registrant prefix
            if arxiv_id:
                original_source = "arxiv"
            else:
                loc_source = (primary_location.get("source") or {})
                original_source = loc_source.get("display_name") or None  # fallback 2
                if not original_source:
                    original_source = _derive_publisher_from_landing_url(  # fallback 3
                        primary_location.get("landing_page_url") or ""
                    )
                if not original_source and doi:
                    original_source = _derive_publisher_from_doi(doi)  # fallback 4
                if not original_source and doi:
                    original_source = self._lookup_publisher_via_crossref(doi)  # fallback 5

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
                primary_topic=primary_topic,
                primary_field=primary_field,
                original_source=original_source,
            )
        except Exception as e:
            logger.warning("openalex_parse_entry_failed", error=str(e))
            return None
