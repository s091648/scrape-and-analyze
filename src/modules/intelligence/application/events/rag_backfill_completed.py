from dataclasses import dataclass


@dataclass(frozen=True)
class RagBackfillCompletedEvent:
    """Event published when the backfill_rag scheduled job finishes."""
    total: int
    succeeded: int
    failed: int
    duration_seconds: float
