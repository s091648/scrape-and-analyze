"""SearchTerm value object — a single autocomplete-suggestible term, scored by how many
distinct articles (within its topic) it occurs in. Immutable, self-validating.

Lives in shared/ (not src/modules/search/domain/) because it's the return shape of
SearchIndexGateway/SqlAlchemySearchTermRepository, both of which backend/ depends on
directly — src/ is not copied into backend's production image (see backend/Dockerfile),
so anything backend imports at runtime must live where both processes can reach it."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchTerm:
    term: str
    occurrence_count: int

    def __post_init__(self) -> None:
        if not self.term:
            raise ValueError("SearchTerm.term must not be empty")
        if self.occurrence_count < 0:
            raise ValueError(f"SearchTerm.occurrence_count must be >= 0, got {self.occurrence_count}")
