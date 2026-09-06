import threading
from dataclasses import dataclass
from typing import List
from uuid import UUID

from .article_outcome import ArticleOutcome


@dataclass
class SourceStats:
    """Accumulates counts of new, duplicate, and failed outcomes for a single source."""
    source: str
    new: int = 0
    duplicate: int = 0
    failed: int = 0


class PipelineStats:
    """Thread-safe collector that tracks per-source article processing outcomes across the pipeline."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sources: dict[str, SourceStats] = {}
        # Article IDs whose scrape+save succeeded (so they count as `new`) but a
        # later stage — analysis / tag normalization / translation / RAG ingestion
        # — failed. Tracked as a de-duplicated set because one article can fail
        # several downstream stages, and RAG failures land here from a separate
        # task/bus, well after the text stage already recorded `new`.
        self._partial_failure_article_ids: set[UUID] = set()

    def record(self, source: str, outcome: ArticleOutcome) -> None:
        """Record an article processing outcome for the given source."""
        with self._lock:
            if source not in self._sources:
                self._sources[source] = SourceStats(source=source)
            s = self._sources[source]
            if outcome == ArticleOutcome.NEW:
                s.new += 1
            elif outcome in (ArticleOutcome.DUPLICATE, ArticleOutcome.DUPLICATE_NEEDS_ANALYSIS):
                s.duplicate += 1
            else:
                s.failed += 1

    def record_partial_failure(self, article_id: UUID | None) -> None:
        """Mark an already-persisted article as having had a downstream stage fail.

        No-op when article_id is None (some FailedEvents carry no article id).
        """
        if article_id is None:
            return
        with self._lock:
            self._partial_failure_article_ids.add(article_id)

    @property
    def partial_failure_count(self) -> int:
        """Number of distinct articles that were saved but failed a later stage."""
        with self._lock:
            return len(self._partial_failure_article_ids)

    def get_results(self) -> List[SourceStats]:
        """Return a list of SourceStats for all recorded sources."""
        with self._lock:
            return list(self._sources.values())
