from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID


@dataclass(frozen=True)
class PendingReconciliation:
    """One openalex-sourced article due for a reconciliation check."""
    article_id: UUID
    work_id: str


class ArticleDedupRepository(ABC):
    """Reconciles articles against upstream (OpenAlex) merge decisions made
    after we'd already scraped one or both sides of a duplicate.

    Merging never deletes a row — the losing article is tombstoned via
    `merged_into_id` so nothing downstream (tags, analyses, favorites,
    failed_tasks) needs cascading cleanup.
    """

    @abstractmethod
    def find_pending_reconciliation(self, limit: int) -> List[PendingReconciliation]:
        """Openalex-sourced, non-tombstoned articles not reconciled in the last
        7 days — OpenAlex's own dedup typically resolves within days of a work
        being indexed, but there's no hard SLA, so candidates keep getting
        re-checked weekly rather than giving up after once."""

    @abstractmethod
    def find_by_work_id(self, work_id: str) -> Optional[UUID]:
        """Return the id of the (non-tombstoned) article with this OpenAlex work_id, or None."""

    @abstractmethod
    def heal_identifiers(self, article_id: UUID, work_id: str, doi: Optional[str]) -> None:
        """Update this article's own metadata to OpenAlex's now-canonical work_id/doi.

        Used when OpenAlex merged this article's work_id away but we never
        scraped the survivor separately — no duplicate row exists to merge with.
        """

    @abstractmethod
    def merge(self, loser_id: UUID, survivor_id: UUID) -> None:
        """Tombstone `loser_id` into `survivor_id`: roll up view_count, union
        tags, and mark `loser_id.merged_into_id = survivor_id`."""

    @abstractmethod
    def mark_reconciled(self, article_id: UUID) -> None:
        """Record that this article's work_id was checked and is still canonical."""
