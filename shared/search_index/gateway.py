from typing import Optional, Protocol
from uuid import UUID

from shared.search_index.search_term import SearchTerm


class SearchIndexGateway(Protocol):
    """Autocomplete suggestion index — a suffix-expanded prefix→ranked-terms structure
    (the "prefix tree", data-model.md). Rebuilt wholesale each scheduled scrape cycle,
    never incrementally mutated. See specs/023-article-search/contracts/search-api.md.
    """

    def rebuild(self, topic_terms: dict[UUID, dict[str, int]]) -> None:
        """Replace the entire index with `topic_terms` (per-topic {term: occurrence_count}
        maps, already document-frequency-filtered by the caller). Atomic — readers never
        see a half-rebuilt index. Never raises; logs a warning and no-ops if the backend
        is unavailable (matches shared/cache's CacheGateway posture)."""
        ...

    def suggest(self, topic_id: Optional[UUID], prefix: str, limit: int = 10) -> Optional[list[SearchTerm]]:
        """Ranked suggestions (by occurrence_count desc) for `prefix` within `topic_id`.

        Returns `None` (not an empty list) when the index is unavailable — either the
        backend errored, or no rebuild has ever completed yet — signaling the caller to
        fall back to the Postgres `search_terms` table (backend/services/search_service.py).
        An empty list is a genuine "no matches" result from a healthy, built index."""
        ...
