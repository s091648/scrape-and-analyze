from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class TagNormalizationCompletedEvent:
    """Published by TagNormalizationHandler after successful tag normalization.

    fix/sanitize: no longer carries article_title/article_content — translation
    used to chain off this event specifically to receive those two fields
    (TagNormalizationHandler fetched them as a courtesy relay). Translation is
    now dispatched independently off AnalysisCompletedEvent (fetching the
    article body itself), so tag normalization failing/being slow no longer
    blocks or delays translation. This event currently has no subscriber —
    kept as a success signal for future consumers (e.g. an admin audit log).
    """
    analysis_id: UUID
    article_id: UUID
    topic_id: Optional[UUID] = None
